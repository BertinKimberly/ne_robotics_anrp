import serial
import platform
import serial.tools.list_ports
from datetime import datetime   
from database import (
    get_vehicle_details, 
    update_vehicle_payment, 
    mark_payment_complete, 
    get_card_balance,
    update_card_balance,
    log_alert,
    update_system_status,
    initialize_database,
    get_db_connection,
    record_payment
)

# Initialize the database
initialize_database()

# Constants
RATE_PER_HOUR = 500  # RWF 500 per hour
MIN_BALANCE = 200  # Minimum balance required

def detect_arduino_port():
    """Detect Arduino port across different operating systems"""
    ports = list(serial.tools.list_ports.comports())
    system = platform.system()
    print(f"[SYSTEM] Operating System: {system}")
    
    for port in ports:
        if system == "Linux" and ("ttyUSB" in port.device or "ttyACM" in port.device):
            return port.device
        elif system == "Darwin" and ("usbmodem" in port.device or "usbserial" in port.device):
            return port.device
        elif system == "Windows" and "COM" in port.device:
            try:
                # Try to open the port
                ser = serial.Serial(port.device, 9600, timeout=1)
                ser.close()
                print(f"[DETECTED] Arduino on {port.device}")
                return port.device
            except:
                continue
    return None

def parse_arduino_data(line):
    """Parse data received from Arduino (plate number and balance)"""
    try:
        # Clean and filter empty lines and headers
        line = line.strip()
        if not line or "***" in line or "----" in line:
            return None, None

        # Handle specific formats
        if "Numberplate:" in line:
            plate = line.split("Numberplate:")[-1].strip()
            if "failed" not in plate:
                return "plate", plate
        elif "Balance:" in line:
            balance = line.split("Balance:")[-1].strip()
            if "failed" not in balance and balance.strip():
                # Clean the balance string and convert to integer
                balance_val = int(''.join(c for c in balance if c.isdigit()))
                return "balance", balance_val
                
        return None, None
    except Exception as e:
        print(f"[ERROR] Parse error: {e}")
        log_alert(None, 'system_error', f'Error parsing Arduino data: {e}')
        return None, None

def calculate_parking_fee(entry_time, exit_time=None):
    """Calculate parking fee based on duration with grace period support and minimum fee
    
    Args:
        entry_time: Entry timestamp (str or datetime)
        exit_time: Exit timestamp (datetime, optional)
        
    Returns:
        float: Calculated parking fee in RWF
    """
    if isinstance(entry_time, str):
        # Handle microseconds by splitting at the dot
        entry_time = entry_time.split('.')[0]
        entry_time = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S')
    
    if exit_time is None:
        exit_time = datetime.now()
    
    # Default grace period of 5 minutes if settings table doesn't exist
    grace_minutes = 5
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = "grace_minutes"')
        result = cursor.fetchone()
        if result:
            grace_minutes = int(result['value'])
        conn.close()
    except Exception as e:
        print(f"[WARNING] Could not fetch grace period from settings: {e}")
    
    # Calculate duration in minutes
    duration = (exit_time - entry_time).total_seconds() / 60
    
    # Always charge at least 1 hour unless within grace period
    if duration <= grace_minutes:
        return RATE_PER_HOUR  # Minimum fee is one hour
        
    # Round up to the nearest hour (any partial hour counts as full hour)
    hours = (int(duration) + 59) // 60  # This ensures proper rounding up
    return hours * RATE_PER_HOUR

def process_payment(plate, balance, ser):
    """Process payment for a vehicle"""
    try:
        # Get vehicle details from database
        vehicle = get_vehicle_details(plate)
        if not vehicle:
            print(f"[ERROR] No unpaid parking record found for {plate}")
            ser.write(b"ERROR:NO_RECORD\n")
            return False

        # If payment is already complete, don't process again
        if vehicle['payment_status'] == 1:
            print(f"[ERROR] Payment already processed for {plate}")
            ser.write(b"ERROR:ALREADY_PAID\n")
            return False

        print(f"[INFO] Found vehicle record: {vehicle}")

        # Calculate fee
        fee = calculate_parking_fee(vehicle['entry_time'])
        print(f"[PAYMENT] Parking fee: {fee} RWF")
        
        # Check if balance is sufficient
        if balance < fee:
            print(f"[ERROR] Insufficient balance: {balance} < {fee}")
            ser.write(f"ERROR:INSUFFICIENT_BALANCE:{fee}\n".encode())
            return False

        try:
            # Update vehicle payment
            update_vehicle_payment(vehicle['id'], fee)
            print("[INFO] Vehicle payment updated")
            
            # Update card balance
            new_balance = balance - fee
            update_card_balance(plate, new_balance)  # Using plate as card_id for now
            print("[INFO] Card balance updated")
            
            # Record the payment
            payment_id = record_payment(vehicle['id'], fee, 'RFID', 'completed')
            if not payment_id:
                print("[ERROR] Failed to record payment")
                ser.write(b"ERROR:PAYMENT_RECORD\n")
                return False
                
            print(f"[INFO] Payment recorded with ID: {payment_id}")
            
            # Mark payment as complete
            mark_payment_complete(vehicle['id'])
            print("[INFO] Payment marked as complete")
            
            # Send success response to Arduino
            ser.write(f"SUCCESS:{new_balance}\n".encode())
            print(f"[SUCCESS] Payment processed. New balance: {new_balance} RWF")
            
            return True
            
        except Exception as db_error:
            print(f"[ERROR] Database update failed: {db_error}")
            ser.write(b"ERROR:DATABASE\n")
            return False

    except Exception as e:
        print(f"[ERROR] Payment processing error: {e}")
        log_alert(vehicle['id'] if vehicle else None, 'payment_error', str(e))
        ser.write(b"ERROR:SYSTEM\n")
        return False

def main():
    """Main function to handle RFID payment processing"""
    port = detect_arduino_port()
    if not port:
        print("[ERROR] No Arduino device found")
        return

    try:
        print(f"[CONNECTED] Listening on {port}")
        ser = serial.Serial(port, 9600, timeout=1)
        current_plate = None
        current_balance = None
        processing_payment = False
        
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8').strip()
                print(f"[SERIAL] Received: {line}")
                
                data_type, value = parse_arduino_data(line)
                
                if data_type == "plate":
                    current_plate = value
                elif data_type == "balance" and not processing_payment:
                    current_balance = value
                    
                # Process payment when we have both plate and balance, but only if not already processing
                if current_plate and current_balance and not processing_payment:
                    processing_payment = True
                    if process_payment(current_plate, current_balance, ser):
                        # Only reset if payment was successful
                        current_plate = None
                        current_balance = None
                    processing_payment = False

    except KeyboardInterrupt:
        print("\n[INFO] Program terminated by user")
    except Exception as e:
        print(f"[ERROR] System error: {e}")
        log_alert(None, 'system_error', str(e))
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    main()