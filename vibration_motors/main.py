import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import json
import time
import threading
import queue

MQTT_BROKER_RECEIVE = "192.168.2.220"  # IP address of the master Raspberry Pi
MQTT_BROKER_RESPONSE = "0.0.0.0"       # Local broker for responses
MQTT_PORT = 1883
MQTT_TOPIC_RECEIVE = "pi4/vibration_motor_controller"
MQTT_TOPIC_RESPONSE = "pi2/vibration_motor_response"

LEFT_MOTOR_PIN = 17
RIGHT_MOTOR_PIN = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(LEFT_MOTOR_PIN, GPIO.OUT)
GPIO.setup(RIGHT_MOTOR_PIN, GPIO.OUT)

GPIO.output(LEFT_MOTOR_PIN, GPIO.LOW)
GPIO.output(RIGHT_MOTOR_PIN, GPIO.LOW)

message_queue = queue.Queue()

left_timer = None
right_timer = None

client_receive = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client_response = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def turn_on_left_motor():
    GPIO.output(LEFT_MOTOR_PIN, GPIO.HIGH)
    print("Left motor ON")

def turn_on_right_motor():
    GPIO.output(RIGHT_MOTOR_PIN, GPIO.HIGH)
    print("Right motor ON")

def turn_off_left_motor():
    GPIO.output(LEFT_MOTOR_PIN, GPIO.LOW)
    print("Left motor OFF")
    
def turn_off_right_motor():
    GPIO.output(RIGHT_MOTOR_PIN, GPIO.LOW)
    print("Right motor OFF")

def send_status_update(message_id, status):
    response = {
        "id": message_id,
        "status": status
    }
    response_json = json.dumps(response)
    client_response.publish(MQTT_TOPIC_RESPONSE, response_json)
    print(f"Published status: {response_json}")

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_RECEIVE)
    print(f"Subscribed to {MQTT_TOPIC_RECEIVE}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print(f"Received message: {payload}")
        
        message_id = payload.get('message_id', 'unknown')
        
        message_queue.put(payload)
        
        send_status_update(message_id, "received")
        
    except json.JSONDecodeError:
        print("Invalid JSON payload")
    except Exception as e:
        print(f"Error processing message: {e}")

def process_queue():
    global left_timer, right_timer
    
    while True:
        try:
            payload = message_queue.get()
            
            message_id = payload.get('message_id', 'unknown')
            left_duration = float(payload.get('left_duration', 0))
            right_duration = float(payload.get('right_duration', 0))
            
            send_status_update(message_id, "processing")
            
            if left_duration > 0:
                if left_timer is not None:
                    left_timer.cancel()
                
                print(f"Left motor ON for {left_duration} seconds")
                turn_on_left_motor()
                
                left_timer = threading.Timer(left_duration, turn_off_left_motor)
                left_timer.start()
            
            if right_duration > 0:
                if right_timer is not None:
                    right_timer.cancel()
                
                print(f"Right motor ON for {right_duration} seconds")
                turn_on_right_motor()
                
                right_timer = threading.Timer(right_duration, turn_off_right_motor)
                right_timer.start()
            
            max_duration = max(left_duration, right_duration)
            if max_duration > 0:
                time.sleep(max_duration + 0.1)
            
            message_queue.task_done()
            
            send_status_update(message_id, "complete")
            
        except Exception as e:
            print(f"Error in queue processing: {e}")

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

queue_thread = threading.Thread(target=process_queue, daemon=True)
queue_thread.start()

try:
    if setup_mqtt_clients():
        print("Starting MQTT loop...")
        client_receive.loop_forever()
    else:
        print("Failed to set up MQTT clients. Exiting.")
    
except KeyboardInterrupt:
    print("Program terminated by user")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    client_response.loop_stop()
    cleanup()