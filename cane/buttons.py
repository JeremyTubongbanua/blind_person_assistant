import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time

# MQTT Configuration
MQTT_BROKER = '127.0.0.1'  # MQTT running on the same Raspberry Pi
MQTT_PORT = 1883
MQTT_TOPIC = "raspberrypi/buttons"

# GPIO Configuration
BUTTON_PINS = [17, 27, 22]  # GPIO17, GPIO27, GPIO22
LONG_PRESS_TIME = 3  # Time in seconds to register a long press
DOUBLE_PRESS_MAX_TIME = 0.5  # Time threshold for detecting a double press

# Setup GPIO
GPIO.setmode(GPIO.BCM)
for pin in BUTTON_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Enable internal pull-down resistors

# MQTT Client Setup (Updated API version)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# Button press tracking
button_timestamps = {pin: [] for pin in BUTTON_PINS}

def detect_press_type(pin):
    current_time = time.time()
    button_timestamps[pin].append(current_time)

    # Remove timestamps older than the long press threshold
    button_timestamps[pin] = [t for t in button_timestamps[pin] if current_time - t <= LONG_PRESS_TIME]

    # Detect long press
    press_start = button_timestamps[pin][0]
    while GPIO.input(pin) == GPIO.HIGH:  # Wait while button is still pressed
        if time.time() - press_start >= LONG_PRESS_TIME:
            event_type = "long_press"
            break
        time.sleep(0.1)
    else:
        # If the button was released before LONG_PRESS_TIME
        if len(button_timestamps[pin]) >= 2 and (button_timestamps[pin][-1] - button_timestamps[pin][-2]) <= DOUBLE_PRESS_MAX_TIME:
            event_type = "double_press"
        else:
            event_type = "single_press"

    # Publish event
    message = {"button": pin, "event": event_type}
    client.publish(MQTT_TOPIC, str(message))
    print(f"Published: {message}")

print("Press buttons to test... (Press Ctrl+C to exit)")

try:
    while True:
        for pin in BUTTON_PINS:
            if GPIO.input(pin) == GPIO.HIGH:  # Button pressed
                print(f"Button {pin} Pressed!")
                detect_press_type(pin)
                time.sleep(0.2)  # Prevent multiple detections for the same press
        time.sleep(0.05)  # Reduce CPU usage

except KeyboardInterrupt:
    GPIO.cleanup()
    client.loop_stop()
    print("\nGPIO Cleanup Done.")
