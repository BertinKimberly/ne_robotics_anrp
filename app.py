from flask import Flask, render_template, jsonify, request
from database import (
    get_db_connection, initialize_database, get_parking_statistics,
    get_occupancy_data, get_revenue_by_hour, get_vehicle_details,
    get_card_balance, update_card_balance, get_settings, update_settings,
    get_revenue_stats, get_occupancy_stats
)
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/')
def index():
    """Main dashboard view"""
    stats = get_parking_statistics(24)  # Get last 24 hours stats
    occupancy = get_occupancy_data()
    return render_template('dashboard.html', stats=stats, occupancy=occupancy)

@app.route('/api/stats')
def get_stats():
    """Get current statistics"""
    time_range = request.args.get('hours', 24, type=int)
    stats = get_parking_statistics(time_range)
    return jsonify(stats)

@app.route('/api/occupancy')
def get_occupancy():
    """Get current occupancy data"""
    data = get_occupancy_data()
    return jsonify(data)

@app.route('/api/revenue/hourly')
def get_hourly_revenue():
    """Get hourly revenue data"""
    hours = request.args.get('hours', 24, type=int)
    data = get_revenue_by_hour(hours)
    return jsonify(data)

@app.route('/api/recent_entries')
def get_recent_entries():
    """Get recent vehicle entries"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT plate_number, entry_time, 
               exit_time, amount_due, payment_status 
        FROM vehicles 
        ORDER BY entry_time DESC LIMIT 10
    ''')
    entries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(entries)

@app.route('/api/recent_alerts')
def get_recent_alerts():
    """Get recent system alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.alert_time, a.alert_type, a.alert_message,
               v.plate_number
        FROM alerts a
        LEFT JOIN vehicles v ON a.vehicle_id = v.id
        ORDER BY a.alert_time DESC LIMIT 10
    ''')
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(alerts)

@app.route('/api/system_status')
def get_system_status():
    """Get current system component status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT component, status, last_checked, message
        FROM system_status
        ORDER BY last_checked DESC
    ''')
    status = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(status)

@app.route('/payments')
def payments_page():
    """Payments page view"""
    return render_template('payments.html')

@app.route('/reports')
def reports_page():
    """Reports page view"""
    return render_template('reports.html')

@app.route('/settings')
def settings_page():
    """Settings page view"""
    return render_template('settings.html')

@app.route('/api/payments')
def get_payments():
    """Get payment records"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            p.id as transaction_id,
            v.plate_number,
            p.amount,
            p.status,
            p.payment_time as date,
            p.payment_method
        FROM payments p
        JOIN vehicles v ON p.vehicle_id = v.id
        ORDER BY p.payment_time DESC
        LIMIT 50
    ''')
    payments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(payments)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update system settings"""
    if request.method == 'POST':
        new_settings = request.json
        success = update_settings(new_settings)
        return jsonify({'success': success})
    else:
        settings = get_settings()
        return jsonify(settings)

@app.route('/api/reports/revenue')
def get_revenue_report():
    """Get revenue statistics"""
    period = request.args.get('period', 'day')  # day, week, month
    stats = get_revenue_stats(period)
    return jsonify(stats)

@app.route('/api/reports/occupancy')
def get_occupancy_report():
    """Get occupancy statistics"""
    period = request.args.get('period', 'day')  # day, week
    stats = get_occupancy_stats(period)
    return jsonify(stats)

@app.route('/api/transaction_history')
def get_transactions():
    """Get transaction history"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            th.id,
            th.transaction_type,
            v.plate_number,
            th.amount,
            th.timestamp,
            th.details
        FROM transaction_history th
        JOIN vehicles v ON th.vehicle_id = v.id
        ORDER BY th.timestamp DESC
        LIMIT ? OFFSET ?
    ''', (per_page, (page - 1) * per_page))
    
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(transactions)

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
