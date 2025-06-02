import cv2
from ultralytics import YOLO
import os
import time
import serial
import serial.tools.list_ports
from collections import Counter
from datetime import datetime

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Database integration
from database import (
    initialize_database, 
    register_vehicle_entry, 
    log_alert,
    update_system_status,
    log_gate_operation,
    validate_vehicle_entry  # Add this import
)

# Load YOLOv8 model
model = YOLO('./brain/best.pt')

# Plate save directory
save_dir = 'plates'
os.makedirs(save_dir, exist_ok=True)

# Initialize database
initialize_database()

# ===== Auto-detect Arduino Serial Port =====
def detect_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "COM" in port.device or "wchusbmodem" in port.device:
            return port.device
    return None

arduino_port = detect_arduino_port()
if arduino_port:
    print(f"[CONNECTED] Arduino on {arduino_port}")
    arduino = serial.Serial(arduino_port, 9600, timeout=1)
    time.sleep(2)
else:
    print("[ERROR] Arduino not detected.")
    arduino = None

def read_distance(arduino):
    """
    Reads a distance (float) value from the Arduino via serial.
    Returns the float if valid, or None if invalid/empty.
    """
    if arduino and arduino.in_waiting > 0:
        try:
            line = arduino.readline().decode('utf-8').strip()
            return float(line)
        except ValueError:
            return None
    return None

# Initialize webcam
cap = cv2.VideoCapture(0)
plate_buffer = []
entry_cooldown = 300  # 5 minutes
last_saved_plate = None
last_entry_time = 0

print("[SYSTEM] Ready. Press 'q' to exit.")

# Initialize system status
update_system_status('camera', 'online', 'Entry camera initialized')
update_system_status('gate_entry', 'online', 'Entry gate ready')

while True:
    ret, frame = cap.read()
    if not ret:
        update_system_status('camera', 'error', 'Failed to read from camera')
        break

    distance = read_distance(arduino)
    print(f"[SENSOR] Distance: {distance} cm")

    if distance is not None and distance <= 50:
        results = model(frame)

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                plate_img = frame[y1:y2, x1:x2]

                # Plate Image Processing
                gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                blur = cv2.GaussianBlur(gray, (5, 5), 0)
                thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

                # OCR Extraction
                plate_text = pytesseract.image_to_string(
                    thresh, config='--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                ).strip().replace(" ", "")

                # Plate Validation
                if "RA" in plate_text:
                    start_idx = plate_text.find("RA")
                    plate_candidate = plate_text[start_idx:]
                    if len(plate_candidate) >= 7:
                        plate_candidate = plate_candidate[:7]
                        prefix, digits, suffix = plate_candidate[:3], plate_candidate[3:6], plate_candidate[6]
                        if (prefix.isalpha() and prefix.isupper() and
                            digits.isdigit() and suffix.isalpha() and suffix.isupper()):
                            print(f"[VALID] Plate Detected: {plate_candidate}")
                            plate_buffer.append(plate_candidate)

                            # Decision after 3 captures
                            if len(plate_buffer) >= 3:
                                most_common = Counter(plate_buffer).most_common(1)[0][0]
                                current_time = time.time()

                                if (most_common != last_saved_plate or
                                    (current_time - last_entry_time) > entry_cooldown):
                                    
                                    # Validate vehicle entry first
                                    can_enter, message = validate_vehicle_entry(most_common)
                                    if not can_enter:
                                        print(f"[ACCESS DENIED] {message}")
                                        log_alert(None, 'unauthorized_entry', f'{message} for plate {most_common}')
                                        if arduino:
                                            arduino.write(b'2')  # Trigger warning buzzer
                                            print("[ALERT] Buzzer triggered (sent '2')")
                                    else:
                                        # Register vehicle in database
                                        vehicle_id = register_vehicle_entry(most_common)
                                        if vehicle_id:
                                            print(f"[SAVED] {most_common} registered in database.")
                                            
                                            # Save plate image with timestamp
                                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                            plate_filename = os.path.join(save_dir, f'plate_{timestamp}.jpg')
                                            cv2.imwrite(plate_filename, plate_img)
                                            
                                            # Open gate
                                            if arduino:
                                                arduino.write(b'1')
                                                print("[GATE] Opening gate (sent '1')")
                                                log_gate_operation('entry', 'open', vehicle_id)
                                                time.sleep(15)  # Gate open duration
                                                arduino.write(b'0')
                                                print("[GATE] Closing gate (sent '0')")
                                                log_gate_operation('entry', 'close', vehicle_id)
                                        else:
                                            print("[ERROR] Failed to register vehicle")
                                            log_alert(None, 'system_error', f'Failed to register plate {most_common}')
                                    
                                    last_saved_plate = most_common
                                    last_entry_time = current_time
                                else:
                                    print("[SKIPPED] Duplicate within 5 min window.")

                                plate_buffer.clear()

                cv2.imshow("Plate", plate_img)
                cv2.imshow("Processed", thresh)
                time.sleep(0.5)

    annotated_frame = results[0].plot() if distance is not None and distance <= 50 else frame
    cv2.imshow('Webcam Feed', annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up
cap.release()
if arduino:
    arduino.close()
update_system_status('camera', 'offline', 'Camera stopped')
update_system_status('gate_entry', 'offline', 'Gate entry system stopped')
cv2.destroyAllWindows()
