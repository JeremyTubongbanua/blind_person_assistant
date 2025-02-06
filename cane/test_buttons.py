import RPi.GPIO as GPIO
import time

BUTTON_PINS = [17, 27, 22]  # GPIO17, GPIO27, GPIO22

GPIO.setmode(GPIO.BCM)
for pin in BUTTON_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Enable internal pull-up resistor

print("Press buttons to test... (Press Ctrl+C to exit)")

try:
    while True:
        for pin in BUTTON_PINS:
            if GPIO.input(pin) == GPIO.HIGH:  # Button pressed (connected to GND)
                print(f"Button {pin} Pressed!")
        time.sleep(0.1)

except KeyboardInterrupt:
    GPIO.cleanup()
    print("\nGPIO Cleanup Done.")