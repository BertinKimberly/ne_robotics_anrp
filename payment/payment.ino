#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9
#define SS_PIN 10

MFRC522 mfrc522(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;
MFRC522::StatusCode card_status;

bool awaitingUpdate = false;
bool sentReady = false;
String currentPlate = "";
String currentBalance = "";

// Timeout variables
unsigned long readySentTime = 0;
const unsigned long RESPONSE_TIMEOUT = 10000; // 10 seconds
const unsigned long RETRY_DELAY = 2000;       // 2 seconds between retries

void setup()
{
    Serial.begin(9600);
    SPI.begin();
    mfrc522.PCD_Init();

    for (byte i = 0; i < 6; i++)
    {
        key.keyByte[i] = 0xFF;
    }

    Serial.println(F("==== PAYMENT MODE RFID ===="));
    Serial.println(F("Place your card near the reader..."));
}

void loop()
{
    if (!awaitingUpdate)
    {
        // Reset values
        currentPlate = "";
        currentBalance = "";

        // Look for new cards
        if (!mfrc522.PICC_IsNewCardPresent())
        {
            return;
        }

        // Select one of the cards
        if (!mfrc522.PICC_ReadCardSerial())
        {
            return;
        }

        // Try to read data with retries
        int retries = 3;
        while (retries > 0)
        {
            currentPlate = readBlockData(4, "Car Plate");
            currentBalance = readBlockData(5, "Balance");

            // If both reads were successful, break the retry loop
            if (!currentPlate.startsWith("[ERROR]") && !currentBalance.startsWith("[ERROR]"))
            {
                break;
            }

            delay(RETRY_DELAY);
            retries--;
        }

        // Only proceed if we have valid data
        if (!currentPlate.startsWith("[ERROR]") && !currentBalance.startsWith("[ERROR]"))
        {
            Serial.println("*** Data from PICC ***");
            Serial.println("Numberplate: " + currentPlate);
            Serial.println("Balance:     " + currentBalance);
            Serial.println("***********************");

            awaitingUpdate = true;
            sentReady = false;
        }

        // Halt PICC and stop encryption
        mfrc522.PICC_HaltA();
        mfrc522.PCD_StopCrypto1();
    }

    // Handle response from Python
    if (awaitingUpdate)
    {
        if (Serial.available())
        {
            String response = Serial.readStringUntil('\n');
            response.trim();

            if (response.startsWith("ERROR:"))
            {
                // Handle different error types
                if (response.indexOf("INSUFFICIENT_BALANCE") >= 0)
                {
                    writeBlockData(5, currentBalance); // Keep old balance
                }
                else if (response.indexOf("NO_RECORD") >= 0)
                {
                    // No action needed
                }
            }
            else if (response.startsWith("SUCCESS:"))
            {
                // Update balance with new value
                String newBalance = response.substring(8);
                writeBlockData(5, newBalance);
            }

            awaitingUpdate = false;
            delay(1000); // Give time for the user to remove the card
        }
    }
}

String readBlockData(byte blockNumber, String label)
{
    byte buffer[18];
    byte bufferSize = sizeof(buffer);

    // Authenticate
    card_status = mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, blockNumber, &key, &(mfrc522.uid));
    if (card_status != MFRC522::STATUS_OK)
    {
        return "[ERROR] Authentication failed for " + label;
    }

    // Read data
    card_status = mfrc522.MIFARE_Read(blockNumber, buffer, &bufferSize);
    if (card_status != MFRC522::STATUS_OK)
    {
        return "[ERROR] Reading failed for " + label;
    }

    String data = "";
    for (uint8_t i = 0; i < 16; i++)
    {
        if (buffer[i] >= 32 && buffer[i] <= 126)
        { // Only print printable ASCII
            data += (char)buffer[i];
        }
    }
    data.trim();
    return data;
}

void writeBlockData(byte blockNumber, String data)
{
    byte buffer[16] = {0}; // Initialize with zeros

    // Clean and prepare data
    data.trim();
    if (data.length() > 16)
    {
        data = data.substring(0, 16);
    }

    // Copy data to buffer
    data.getBytes(buffer, data.length() + 1);

    // Authenticate
    card_status = mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, blockNumber, &key, &(mfrc522.uid));
    if (card_status != MFRC522::STATUS_OK)
    {
        Serial.println("[ERROR] Authentication failed for write");
        return;
    } // Write data
    card_status = mfrc522.MIFARE_Write(blockNumber, buffer, 16);
    if (card_status != MFRC522::STATUS_OK)
    {
        Serial.println("[ERROR] Writing failed");
        return;
    }

    // Verify the written data
    byte verifyBuffer[18];
    byte verifySize = sizeof(verifyBuffer);
    card_status = mfrc522.MIFARE_Read(blockNumber, verifyBuffer, &verifySize);
    if (card_status != MFRC522::STATUS_OK)
    {
        Serial.println("[ERROR] Verification read failed");
        return;
    }

    // Compare written data
    bool verified = true;
    for (uint8_t i = 0; i < 16; i++)
    {
        if (buffer[i] != verifyBuffer[i])
        {
            verified = false;
            break;
        }
    }

    if (!verified)
    {
        Serial.println("[ERROR] Data verification failed");
        return;
    }

    Serial.println("[SUCCESS] Data written and verified");
}
