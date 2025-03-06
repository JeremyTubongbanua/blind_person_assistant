import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import json
import time
from time import sleep
import threading

MQTT_BROKER_RECEIVE = "192.168.2.220"
MQTT_BROKER_RESPONSE = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC_RECEIVE = "pi4/vibration_motor_controller"
MQTT_TOPIC_RESPONSE = "pi2/vibration_motor_response"

LEFT_MOTOR_PIN = 22
RIGHT_MOTOR_PIN = 17

MESSAGE_TIMEOUT_SECONDS = 1.5

GPIO.setmode(GPIO.BCM)
GPIO.setup(LEFT_MOTOR_PIN, GPIO.OUT)
GPIO.setup(RIGHT_MOTOR_PIN, GPIO.OUT)

GPIO.output(LEFT_MOTOR_PIN, GPIO.LOW)
GPIO.output(RIGHT_MOTOR_PIN, GPIO.LOW)

left_timer = None
right_timer = None
current_command_id = None

client_receive = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client_response = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def turn_on_left_motor():
    GPIO.output(LEFT_MOTOR_PIN, GPIO.HIGH)
    print("Left motor ON")
    return time.time()

def turn_on_right_motor():
    GPIO.output(RIGHT_MOTOR_PIN, GPIO.HIGH)
    print("Right motor ON")
    return time.time()

def turn_off_left_motor():
    GPIO.output(LEFT_MOTOR_PIN, GPIO.LOW)
    print("Left motor OFF")
    
def turn_off_right_motor():
    GPIO.output(RIGHT_MOTOR_PIN, GPIO.LOW)
    print("Right motor OFF")

def send_processing_status(message_id, left_motor_time=None, right_motor_time=None):
    response = {
        "id": message_id,
        "status": "processing"
    }
    
    if left_motor_time is not None:
        response["left_motor_trigger_time"] = left_motor_time
    
    if right_motor_time is not None:
        response["right_motor_trigger_time"] = right_motor_time
        
    response_json = json.dumps(response)
    client_response.publish(MQTT_TOPIC_RESPONSE, response_json)
    print(f"Published processing status: {response_json}")

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_RECEIVE)
    print(f"Subscribed to {MQTT_TOPIC_RECEIVE}")

def on_message(client, userdata, msg):
    global left_timer, right_timer, current_command_id
    
    try:
        payload = json.loads(msg.payload.decode())
        print(f"Received message: {payload}")
        
        message_id = payload.get('message_id', 'unknown')
        message_timestamp = payload.get('timestamp', 0)
        current_time = time.time()
        
        # Check if message is too old
        if message_timestamp and current_time - message_timestamp > MESSAGE_TIMEOUT_SECONDS:
            time_diff = current_time - message_timestamp
            print(f"Message too late: {time_diff} seconds (threshold: {MESSAGE_TIMEOUT_SECONDS} seconds)")
            return
        
        # Set this as the current command
        current_command_id = message_id
        
        # Cancel any active timers
        if left_timer is not None:
            left_timer.cancel()
            left_timer = None
        
        if right_timer is not None:
            right_timer.cancel()
            right_timer = None
        
        # Ensure motors are off before starting new command
        turn_off_left_motor()
        turn_off_right_motor()
        
        left_duration = float(payload.get('left_duration', 0))
        right_duration = float(payload.get('right_duration', 0))
        
        left_motor_time = None
        right_motor_time = None
        
        if left_duration > 0:
            print(f"Left motor ON for {left_duration} seconds")
            left_motor_time = turn_on_left_motor()
            
            left_timer = threading.Timer(left_duration, turn_off_left_motor)
            left_timer.start()
        
        if right_duration > 0:
            print(f"Right motor ON for {right_duration} seconds")
            right_motor_time = turn_on_right_motor()
            
            right_timer = threading.Timer(right_duration, turn_off_right_motor)
            right_timer.start()
        
        # Send the processing status once motors are activated
        send_processing_status(message_id, left_motor_time, right_motor_time)
        
        # Clear current command if motors weren't activated
        if max(left_duration, right_duration) <= 0:
            current_command_id = None
        
    except json.JSONDecodeError:
        print("Invalid JSON payload")
    except Exception as e:
        print(f"Error processing message: {e}")

def cleanup():
    turn_off_left_motor()
    turn_off_right_motor()
    GPIO.cleanup()
    print("GPIO cleaned up")
    
    if left_timer is not None:
        left_timer.cancel()
    if right_timer is not None:
        right_timer.cancel()

def setup_mqtt_clients():
    client_receive.on_connect = on_connect
    client_receive.on_message = on_message
    
    print(f"Connecting response client to MQTT broker at {MQTT_BROKER_RESPONSE}:{MQTT_PORT}")
    try:
        client_response.connect(MQTT_BROKER_RESPONSE, MQTT_PORT, 60)
        client_response.loop_start()
        print("Response client connected successfully")
    except Exception as e:
        print(f"Failed to connect response client: {e}")
        return False
    
    print(f"Connecting receive client to MQTT broker at {MQTT_BROKER_RECEIVE}:{MQTT_PORT}")
    try:
        client_receive.connect(MQTT_BROKER_RECEIVE, MQTT_PORT, 60)
        print("Receive client connected successfully")
        return True
    except Exception as e:
        print(f"Failed to connect receive client: {e}")
        client_response.loop_stop()
        return False

try:
    if setup_mqtt_clients():
        print("Starting MQTT loop...")
        turn_on_left_motor()
        turn_on_right_motor()
        sleep(0.1)
        turn_off_left_motor()
        turn_off_right_motor()
        sleep(0.3)
        turn_on_left_motor()
        turn_on_right_motor()
        sleep(0.1)
        turn_off_left_motor()
        turn_off_right_motor()
        client_receive.loop_forever()
        # vibrate for 0.5 seconds for both
    else:
        print("Failed to set up MQTT clients. Exiting.")
    
except KeyboardInterrupt:
    print("Program terminated by user")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    client_response.loop_stop()
    cleanup()