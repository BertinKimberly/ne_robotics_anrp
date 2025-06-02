# Automated Parking Management System

A cutting-edge parking management solution developed by NEW MARS Company in Kigali City. This system integrates Automatic Number Plate Recognition (ANPR), RFID-based payments, and proximity sensing to provide a seamless parking experience.

## 🚗 Features

-  **Vehicle Registration**

   -  Automatic license plate detection using ANPR
   -  Entry timestamp recording
   -  Real-time vehicle detection using proximity sensors

-  **RFID Payment System**

   -  Cost: RWF 500 per hour (rounded up)
   -  RFID card-based payment processing
   -  Balance management system

-  **Smart Exit Control**

   -  Payment verification before exit
   -  Automated gate operation
   -  License plate recognition at exit

-  **Security Features**

   -  Tampering detection
   -  Alert system with logging
   -  Incident recording with timestamps

-  **Monitoring Dashboard**
   -  Real-time entry/exit logs
   -  Payment tracking
   -  Security alert display

## 🛠️ System Architecture

### Hardware Components

-  Laptop with camera
-  Arduino UNO microcontroller
-  RFID Development Kit
   -  RFID Reader
   -  RFID Cards
   -  Jumper wires (7x male-to-female)
-  Gate Control System
   -  2x Barrier Stands
   -  Barrier Stick
   -  Stepper Motor with ULN2003AN driver
   -  Ultrasonic Sensor
   -  Piezo Buzzer
   -  LEDs (Red & Green)
   -  2x 150-ohm Resistors
   -  Mini Breadboard
   -  Jumper wires (18x male-to-female, 18x male-to-male)
   -  Demo car with license plate

### Software Stack

-  **Languages**

   -  Python (Backend & Computer Vision)
   -  C/C++ (Arduino)
   -  HTML/CSS/JavaScript (Frontend)
   -  SQL (Database)

-  **Libraries & Frameworks**
   -  OpenCV (Computer Vision)
   -  pytesseract (OCR)
   -  YOLO (Object Detection)
   -  Flask (Web Dashboard)
   -  SQLite3 (Database)
   -  pyserial (Arduino Communication)
   -  MFRC522 (RFID Operations)
   -  Bootstrap (UI)
   -  Chart.js (Dashboard Visualization)

## 📁 Project Structure

```
parking-management-system/
├── app.py                 # Main application entry point
├── car_entry.py          # Entry gate control & ANPR
├── car_exit.py           # Exit gate control & verification
├── dashboard.py          # Web dashboard implementation
├── database.py           # Database operations & schema
├── process_payment.py    # RFID payment processing
├── brain/                # YOLO models for ANPR
├── exit_gate/           # Arduino code for exit gate
├── payment/             # RFID payment system code
└── templates/           # Dashboard HTML templates
```

## 🚀 Setup & Installation

1. **Hardware Setup**

   -  Connect Arduino UNO to computer
   -  Wire RFID reader according to pinout diagram
   -  Set up gate control components

2. **Software Requirements**

   ```bash
   pip install -r requirements.txt
   ```

3. **Database Initialization**

   ```bash
   python reinit_db.py
   ```

4. **Arduino Code Upload**
   -  Upload `exit_gate.ino` to exit gate Arduino
   -  Upload `payment.ino` to payment system Arduino

## 💡 Usage

1. **Starting the System**

   ```bash
   python app.py
   ```

2. **Accessing the Dashboard**

   -  Open browser to `http://localhost:5000`

3. **Vehicle Entry Process**

   -  Vehicle approaches entry gate
   -  System captures license plate
   -  Gate opens upon successful registration

4. **Payment Process**

   -  Tap RFID card at payment terminal
   -  System calculates fee based on duration
   -  Payment processed from card balance

5. **Exit Process**
   -  Vehicle approaches exit gate
   -  System verifies payment status
   -  Gate opens for paid vehicles

## 🔒 Security Features

-  Unauthorized exit detection
-  Real-time alert system
-  Incident logging with plate numbers
-  Payment verification
-  Gate tampering detection

## 📊 Monitoring & Analytics

The dashboard provides:

-  Real-time occupancy stats
-  Revenue tracking
-  Security incident logs
-  Vehicle entry/exit history

## ⚠️ Alert System

The system generates alerts for:

-  Unauthorized exits
-  Payment failures
-  Gate tampering attempts
-  System malfunctions

## 📝 License

Copyright © 2025 NEW MARS Company, Kigali City

---

For technical support or inquiries, please contact the development team.
