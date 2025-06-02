import os
import sqlite3
from database import DATABASE_FILE

def force_reinit_settings():
    """Force reinitialize the settings table"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Recreate settings table
        cursor.execute('DROP TABLE IF EXISTS settings')
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
        cursor.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', default_settings)
        conn.commit()
        print("Settings table reinitialized successfully")
        
    except Exception as e:
        print(f"Error reinitializing settings table: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    force_reinit_settings()
