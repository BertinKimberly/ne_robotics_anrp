import csv
import sqlite3
from datetime import datetime
from database import initialize_database, DATABASE_FILE
import os

def migrate_csv_to_sqlite():
    """Migrate data from CSV files to SQLite database"""
    print("Starting migration process...")
    
    # Initialize the database first
    initialize_database()
    
    # Connect to SQLite database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Migrate from plates_log.csv
    if os.path.exists('plates_log.csv'):
        print("Migrating from plates_log.csv...")
        with open('plates_log.csv', 'r') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            for row in csv_reader:
                try:
                    # Convert the CSV data to match our new schema
                    plate_number = row.get('car_plate', '')
                    entry_time = row.get('entry_time', '')
                    exit_time = row.get('exit_time', '')
                    amount_due = float(row.get('due_payment', 0)) if row.get('due_payment') else 0
                    payment_status = int(row.get('payment_status', 0))
                    
                    # Insert into vehicles table
                    cursor.execute('''
                        INSERT OR IGNORE INTO vehicles 
                        (plate_number, entry_time, exit_time, amount_due, payment_status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (plate_number, entry_time, exit_time if exit_time else None, 
                         amount_due, payment_status))
                    
                    # If payment was made, record it in payments table
                    if payment_status == 1:
                        vehicle_id = cursor.lastrowid
                        cursor.execute('''
                            INSERT INTO payments (vehicle_id, amount, payment_time)
                            VALUES (?, ?, ?)
                        ''', (vehicle_id, amount_due, exit_time if exit_time else datetime.now()))
                
                except Exception as e:
                    print(f"Error processing row: {row}")
                    print(f"Error details: {e}")
                    continue
    
    # Migrate from testdb.csv if it exists
    if os.path.exists('testdb.csv'):
        print("Migrating from testdb.csv...")
        with open('testdb.csv', 'r') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            for row in csv_reader:
                try:
                    plate_number = row.get('car_plate', '')
                    entry_time = row.get('entry_time', '')
                    exit_time = row.get('exit_time', '')
                    amount_due = float(row.get('due_payment', 0)) if row.get('due_payment') else 0
                    payment_status = int(row.get('payment_status', 0))
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO vehicles 
                        (plate_number, entry_time, exit_time, amount_due, payment_status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (plate_number, entry_time, exit_time if exit_time else None, 
                         amount_due, payment_status))
                    
                except Exception as e:
                    print(f"Error processing row: {row}")
                    print(f"Error details: {e}")
                    continue
    
    # Commit all changes
    conn.commit()
    
    # Print migration statistics
    cursor.execute('SELECT COUNT(*) FROM vehicles')
    vehicle_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM payments')
    payment_count = cursor.fetchone()[0]
    
    print("\nMigration completed!")
    print(f"Total vehicles migrated: {vehicle_count}")
    print(f"Total payments migrated: {payment_count}")
    
    conn.close()

if __name__ == "__main__":
    migrate_csv_to_sqlite()
