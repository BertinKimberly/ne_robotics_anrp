import sqlite3
from datetime import datetime
import os

DATABASE_FILE = 'parking.db'

def initialize_database():
    """Create database and tables if they don't exist"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Create settings table first
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings
        default_settings = [
            ('parking_rate', '500'),
            ('max_capacity', '100'),
            ('grace_minutes', '15'),
            ('alert_threshold', '90'),
            ('auto_lock_gate', 'true'),
            ('enable_notifications', 'true')
        ]
        
        # Use INSERT OR IGNORE to add default settings
        cursor.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', default_settings)
        
        # Create vehicles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL,
                entry_time DATETIME,
                exit_time DATETIME,
                amount_due DECIMAL(10,2),
                payment_status INTEGER DEFAULT 0,
                UNIQUE(plate_number, entry_time)
            )
        ''')
        
        # Create payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER,
                amount DECIMAL(10,2),
                payment_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                payment_method TEXT DEFAULT 'RFID',
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER,
                alert_type TEXT,
                alert_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                alert_message TEXT,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')
        
        # Create rfid_cards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rfid_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT UNIQUE,
                balance DECIMAL(10,2) DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create gate_operations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gate_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gate_location TEXT NOT NULL,  -- 'entry' or 'exit'
                operation_type TEXT NOT NULL, -- 'open' or 'close'
                vehicle_id INTEGER,
                operation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                success INTEGER DEFAULT 1,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')

        # Create system_status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,  -- 'camera', 'rfid_reader', 'gate_entry', 'gate_exit'
                status TEXT NOT NULL,     -- 'online', 'offline', 'error'
                last_checked DATETIME DEFAULT CURRENT_TIMESTAMP,
                message TEXT
            )
        ''')

        # Create transaction_history table for detailed reporting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type TEXT NOT NULL,  -- 'entry', 'exit', 'payment'
                vehicle_id INTEGER,
                amount DECIMAL(10,2),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')
        
        conn.commit()
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Vehicle operations
def register_vehicle_entry(plate_number):
    """Register a new vehicle entry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if vehicle already has an active session
        cursor.execute('''
            SELECT id, entry_time FROM vehicles 
            WHERE plate_number = ? AND exit_time IS NULL
        ''', (plate_number,))
        existing = cursor.fetchone()
        if existing:
            return None  # Vehicle already inside
            
        # Check if vehicle has any unpaid sessions
        cursor.execute('''
            SELECT id FROM vehicles 
            WHERE plate_number = ? 
            AND payment_status = 0 
            AND exit_time IS NULL
        ''', (plate_number,))
        unpaid = cursor.fetchone()
        if unpaid:
            return None  # Has unpaid session
            
        entry_time = datetime.now()
        cursor.execute('''
            INSERT INTO vehicles (plate_number, entry_time)
            VALUES (?, ?)
        ''', (plate_number, entry_time))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_vehicle_details(plate_number):
    """Get vehicle details including payment status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM vehicles
        WHERE plate_number = ? AND payment_status = 0
        ORDER BY entry_time DESC LIMIT 1
    ''', (plate_number,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None

def update_vehicle_payment(vehicle_id, amount_due):
    """Update vehicle payment details without setting exit_time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vehicles
        SET amount_due = ?
        WHERE id = ?
    ''', (amount_due, vehicle_id))
    conn.commit()
    conn.close()

def mark_payment_complete(vehicle_id):
    """Mark a vehicle's payment as complete"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vehicles
        SET payment_status = 1
        WHERE id = ?
    ''', (vehicle_id,))
    conn.commit()
    conn.close()

# RFID operations
def get_card_balance(card_id):
    """Get RFID card balance"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM rfid_cards WHERE card_id = ?', (card_id,))
    result = cursor.fetchone()
    conn.close()
    return result['balance'] if result else 0

def update_card_balance(card_id, new_balance):
    """Update RFID card balance"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO rfid_cards (card_id, balance, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (card_id, new_balance))
    conn.commit()
    conn.close()

# Alert operations
def log_alert(vehicle_id, alert_type, message):
    """Log a new alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (vehicle_id, alert_type, alert_message)
        VALUES (?, ?, ?)
    ''', (vehicle_id, alert_type, message))
    conn.commit()
    conn.close()

# Gate operations
def log_gate_operation(gate_location, operation_type, vehicle_id=None, success=True):
    """Log a gate operation"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO gate_operations (gate_location, operation_type, vehicle_id, success)
        VALUES (?, ?, ?, ?)
    ''', (gate_location, operation_type, vehicle_id, 1 if success else 0))
    conn.commit()
    conn.close()

def update_system_status(component, status, message=None):
    """Update system component status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO system_status (component, status, message)
        VALUES (?, ?, ?)
    ''', (component, status, message))
    conn.commit()
    conn.close()

# Statistics and dashboard functions
def get_parking_statistics(time_range=24):
    """Get parking statistics for the dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate the timestamp for the time range (hours)
    time_threshold = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_entries,
            SUM(CASE WHEN exit_time IS NOT NULL THEN 1 ELSE 0 END) as total_exits,
            SUM(CASE WHEN payment_status = 1 THEN 1 ELSE 0 END) as completed_payments,
            SUM(amount_due) as total_revenue
        FROM vehicles 
        WHERE entry_time >= datetime(?, ?)
    ''', (time_threshold, f'-{time_range} hours'))
    
    stats = dict(cursor.fetchone())
    
    # Get recent alerts
    cursor.execute('''
        SELECT COUNT(*) as alert_count
        FROM alerts
        WHERE alert_time >= datetime(?, ?)
    ''', (time_threshold, f'-{time_range} hours'))
    
    stats.update(dict(cursor.fetchone()))
    conn.close()
    return stats

def get_occupancy_data():
    """Get current parking occupancy data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_vehicles,
            SUM(CASE WHEN exit_time IS NULL THEN 1 ELSE 0 END) as current_occupancy
        FROM vehicles
    ''')
    
    data = dict(cursor.fetchone())
    conn.close()
    return data

def get_revenue_by_hour(hours=24):
    """Get revenue data by hour for charts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            strftime('%Y-%m-%d %H:00:00', payment_time) as hour,
            SUM(amount) as revenue
        FROM payments
        WHERE payment_time >= datetime('now', ?)
        GROUP BY hour
        ORDER BY hour
    ''', (f'-{hours} hours',))
    
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return data

def can_vehicle_enter(plate_number):
    """Check if vehicle can enter (not already inside)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id FROM vehicles 
            WHERE plate_number = ? AND exit_time IS NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        result = cursor.fetchone()
        return result is None  # Can enter if no active session found
    finally:
        conn.close()

def can_vehicle_exit(plate_number):
    """Check if vehicle can exit (has paid entry)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, payment_status
            FROM vehicles
            WHERE plate_number = ? AND exit_time IS NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        result = cursor.fetchone()
        
        if not result:
            return False  # Vehicle not found in system
            
        return result['payment_status'] == 1  # 1 means paid, 0 means unpaid
        
    finally:
        conn.close()
 

def record_vehicle_exit(plate_number):
    """Record vehicle exit time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        exit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE vehicles 
            SET exit_time = ?
            WHERE plate_number = ? 
                AND exit_time IS NULL 
                AND payment_status = 1
                AND id = (
                    SELECT id FROM vehicles 
                    WHERE plate_number = ? 
                    AND exit_time IS NULL 
                    ORDER BY entry_time DESC 
                    LIMIT 1
                )
        ''', (exit_time, plate_number, plate_number))
        
        success = cursor.rowcount > 0
        conn.commit()
        return success
        
    finally:
        conn.close()

def is_vehicle_inside(plate_number):
    """Check if a vehicle is currently inside the parking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id FROM vehicles 
            WHERE plate_number = ? 
            AND exit_time IS NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        result = cursor.fetchone()
        return result is not None  # True if vehicle is inside
    finally:
        conn.close()

def validate_vehicle_entry(plate_number):
    """Validate if a vehicle can enter the parking area"""
    if is_vehicle_inside(plate_number):
        return False, "Vehicle is already inside"
    return True, "Vehicle can enter"

def validate_vehicle_exit(plate_number):
    """Validate if a vehicle can exit the parking area"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First check if vehicle is actually inside
        cursor.execute('''
            SELECT id, payment_status, entry_time, amount_due
            FROM vehicles
            WHERE plate_number = ? 
            AND exit_time IS NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        result = cursor.fetchone()
        
        if not result:
            return False, "Vehicle not found in system or has already exited"
            
        if result['payment_status'] == 0:
            if result['amount_due'] is None:
                return False, "Payment not yet calculated"
            return False, f"Payment required before exit (Amount: ${result['amount_due']:.2f})"
            
        return True, "Vehicle can exit"
    finally:
        conn.close()

def validate_vehicle_payment(plate_number):
    """Validate if a vehicle needs to make a payment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, payment_status, entry_time, amount_due, exit_time
            FROM vehicles
            WHERE plate_number = ? 
            AND exit_time IS NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (plate_number,))
        result = cursor.fetchone()
        
        if not result:
            return False, "No active parking session found"
            
        if result['exit_time'] is not None:
            return False, "Vehicle has already exited"
            
        if result['payment_status'] == 1:
            return False, "Payment has already been completed"
            
        if result['amount_due'] is None:
            return False, "Payment amount not yet calculated"
            
        return True, f"Payment required: ${result['amount_due']:.2f}"
    finally:
        conn.close()
 

def get_settings():
    """Get all system settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    settings = dict(cursor.fetchall())
    conn.close()
    return settings

def update_settings(settings_dict):
    """Update system settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    for key, value in settings_dict.items():
        cursor.execute('''
            INSERT INTO settings (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET 
                value=excluded.value, 
                updated_at=CURRENT_TIMESTAMP
        ''', (key, str(value)))
    conn.commit()
    conn.close()
    return True

def get_revenue_stats(period='day'):
    """Get revenue statistics for a specific period"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if period == 'day':
        interval = 'time'
        group_by = "strftime('%H', payment_time)"
        time_filter = "payment_time >= datetime('now', '-1 day')"
    elif period == 'week':
        interval = 'date'
        group_by = "strftime('%Y-%m-%d', payment_time)"
        time_filter = "payment_time >= datetime('now', '-7 days')"
    else:  # month
        interval = 'date'
        group_by = "strftime('%Y-%m-%d', payment_time)"
        time_filter = "payment_time >= datetime('now', '-30 days')"
    
    cursor.execute(f'''
        SELECT 
            {group_by} as {interval},
            SUM(amount) as total_revenue,
            COUNT(*) as transaction_count
        FROM payments
        WHERE {time_filter}
        GROUP BY {group_by}
        ORDER BY {interval}
    ''')
    
    stats = cursor.fetchall()
    conn.close()
    return [dict(row) for row in stats]

def get_occupancy_stats(period='day'):
    """Get occupancy statistics for a specific period"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if period == 'day':
        interval = 'hour'
        group_by = "strftime('%H', entry_time)"
        time_filter = "entry_time >= datetime('now', '-1 day')"
    else:
        interval = 'date'
        group_by = "strftime('%Y-%m-%d', entry_time)"
        time_filter = "entry_time >= datetime('now', '-7 days')"
    
    cursor.execute(f'''
        SELECT 
            {group_by} as {interval},
            COUNT(*) as entries,
            AVG(CASE WHEN exit_time IS NULL THEN 1 ELSE 0 END) * 100 as occupancy_rate
        FROM vehicles
        WHERE {time_filter}
        GROUP BY {group_by}
        ORDER BY {interval}
    ''')
    
    stats = cursor.fetchall()
    conn.close()
    return [dict(row) for row in stats]

def record_transaction(transaction_type, vehicle_id, amount=None, details=None):
    """Record a transaction in the history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO transaction_history 
        (transaction_type, vehicle_id, amount, details)
        VALUES (?, ?, ?, ?)
    ''', (transaction_type, vehicle_id, amount, details))
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def record_payment(vehicle_id, amount, payment_method='RFID', status='completed'):
    """Record a payment in the payments table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO payments (vehicle_id, amount, payment_method, status)
            VALUES (?, ?, ?, ?)
        ''', (vehicle_id, amount, payment_method, status))
        payment_id = cursor.lastrowid
        conn.commit()
        return payment_id
    except Exception as e:
        print(f"Error recording payment: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_database()
