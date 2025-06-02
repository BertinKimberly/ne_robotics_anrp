from flask import Flask, render_template
from database import get_db_connection
from datetime import datetime, timedelta

app = Flask(__name__)

def get_current_stats():
    """Get current parking statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get vehicles currently inside
    cursor.execute('''
        SELECT COUNT(*) as count FROM vehicles 
        WHERE exit_time IS NULL
    ''')
    vehicles_inside = cursor.fetchone()['count']
    
    # Get max capacity from settings
    cursor.execute('SELECT value FROM settings WHERE key = "max_capacity"')
    max_capacity = int(cursor.fetchone()['value'])
    
    # Calculate available spaces
    available_spaces = max_capacity - vehicles_inside
    
    # Get today's revenue
    today = datetime.now().date()
    cursor.execute('''
        SELECT SUM(amount_due) as revenue FROM vehicles 
        WHERE DATE(exit_time) = ? AND payment_status = 1
    ''', (today,))
    revenue = cursor.fetchone()['revenue'] or 0
    
    conn.close()
    return {
        'vehicles_inside': vehicles_inside,
        'available_spaces': available_spaces,
        'today_revenue': revenue
    }

def get_recent_activities():
    """Get recent vehicle activities"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get last 10 activities (entries, exits, payments)
    cursor.execute('''
        SELECT 
            v.plate_number,
            v.entry_time,
            CASE 
                WHEN v.exit_time IS NULL THEN 'Entry'
                ELSE 'Exit'
            END as event,
            CASE
                WHEN v.payment_status = 1 THEN 'Paid'
                ELSE 'Pending'
            END as status
        FROM vehicles v
        ORDER BY 
            COALESCE(v.exit_time, v.entry_time) DESC
        LIMIT 10
    ''')
    activities = []
    for row in cursor.fetchall():
        activities.append({
            'timestamp': row['entry_time'],
            'plate': row['plate_number'],
            'event': row['event'],
            'status': row['status']
        })
    
    conn.close()
    return activities

def get_recent_alerts():
    """Get recent alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT alert_type, alert_time, alert_message
        FROM alerts
        ORDER BY alert_time DESC
        LIMIT 10
    ''')
    alerts = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return alerts

@app.route('/')
def dashboard():
    """Render the main dashboard"""
    stats = get_current_stats()
    activities = get_recent_activities()
    alerts = get_recent_alerts()
    
    return render_template('dashboard.html',
                         stats=stats,
                         activities=activities,
                         alerts=alerts)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
