import RPi.GPIO as GPIO
import time
import json
import paho.mqtt.client as mqtt

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/button_state"

BUTTON_PIN_1 = 26
BUTTON_PIN_2 = 16

def setup_gpio():
    """
    Initialize GPIO pins for button input with pull-up resistors.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_PIN_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def setup_mqtt():
    """
    Initialize and connect to the MQTT broker.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    return client

def read_button_states():
    """
    Read the current state of both buttons.
    
    Returns:
        tuple: (button1_pressed, button2_pressed)
    """
    state_button1 = GPIO.input(BUTTON_PIN_1)
    state_button2 = GPIO.input(BUTTON_PIN_2)
    
    button1_pressed = state_button1 == GPIO.LOW
    button2_pressed = state_button2 == GPIO.LOW
    
    return button1_pressed, button2_pressed

def publish_button_states(client, button1_pressed, button2_pressed):
    """
    Publish button states to the MQTT topic.
    
    Args:
        client: MQTT client instance
        button1_pressed: Boolean indicating if button 1 is pressed
        button2_pressed: Boolean indicating if button 2 is pressed
    """
    payload = {
        "button1": button1_pressed,
        "button2": button2_pressed,
        "timestamp": time.time()
    }
    
    message = json.dumps(payload)
    client.publish(MQTT_TOPIC, message)
    return payload

def main():
    """
    Main function to run the button state monitoring and MQTT publishing.
    """
    setup_gpio()
    mqtt_client = setup_mqtt()
    
    prev_button1_state = False
    prev_button2_state = False
    
    try:
        while True:
            button1_pressed, button2_pressed = read_button_states()
            
            if button1_pressed != prev_button1_state or button2_pressed != prev_button2_state:
                payload = publish_button_states(mqtt_client, button1_pressed, button2_pressed)
                print(f"Published: {payload}")
                
                prev_button1_state = button1_pressed
                prev_button2_state = button2_pressed
            
            # print(f"Button 1: {'Pressed' if button1_pressed else 'Released'}")
            # print(f"Button 2: {'Pressed' if button2_pressed else 'Released'}")
            # print("-" * 30)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Exiting program")
    finally:
        mqtt_client.loop_stop()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
