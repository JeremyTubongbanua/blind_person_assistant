import RPi.GPIO as GPIO
import time

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Define button pins
BUTTON_PIN_1 = 26
BUTTON_PIN_2 = 16

# Set up button pins as input
# For example, if the buttons are wired to pull the pin to ground when pressed,
# use the internal pull-up resistor.
GPIO.setup(BUTTON_PIN_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_PIN_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    while True:
        # Read button states
        state_button1 = GPIO.input(BUTTON_PIN_1)
        state_button2 = GPIO.input(BUTTON_PIN_2)
        
        # For pull-up configuration: GPIO.input returns False when the button is pressed
        # Print the button states.
        print(f"Button on GPIO {BUTTON_PIN_1}: {'Pressed' if state_button1 == GPIO.LOW else 'Released'}")
        print(f"Button on GPIO {BUTTON_PIN_2}: {'Pressed' if state_button2 == GPIO.LOW else 'Released'}")
        print("-" * 30)
        
        # Wait for 0.5 seconds
        time.sleep(0.5)
except KeyboardInterrupt:
    print("Exiting program")
finally:
    GPIO.cleanup()
