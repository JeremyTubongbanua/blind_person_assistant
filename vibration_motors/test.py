import RPi.GPIO as GPIO
import time

# Use BCM GPIO numbering
GPIO.setmode(GPIO.BCM)

# Define the relay pins
RELAY_PIN = 17
RELAY2_PIN = 22

# Set up the relay pins as outputs
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.setup(RELAY2_PIN, GPIO.OUT)

try:
    while True:
        # Turn relay 1 on and relay 2 off
        GPIO.output(RELAY2_PIN, GPIO.LOW)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        print("Relay 1 ON, Relay 2 OFF")
        time.sleep(1)
        
        # Turn relay 1 off and relay 2 on
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        GPIO.output(RELAY2_PIN, GPIO.HIGH)
        print("Relay 1 OFF, Relay 2 ON")
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting program")
finally:
    # Clean up GPIO states when the program is terminated.
    GPIO.cleanup()
