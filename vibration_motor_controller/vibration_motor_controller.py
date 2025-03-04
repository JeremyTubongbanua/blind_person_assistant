import json
import uuid
import threading
import time
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
from queue import Queue
from threading import Event

MQTT_BROKER_LOCAL = "0.0.0.0"
MQTT_BROKER_RESPONSE = "192.168.2.219"
MQTT_PORT = 1883
MQTT_TOPIC_PUBLISH = "pi4/vibration_motor_controller"
MQTT_TOPIC_RESPONSE = "pi2/vibration_motor_response" 
MAX_WAIT_TIME = 10

app = Flask(__name__)

response_events = {}
response_data = {}
response_lock = threading.Lock()

client_publish = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client_subscribe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect_subscribe(client, userdata, flags, rc, properties=None):
    print(f"Connected to MQTT response broker with result code: {rc}")
    client.subscribe(MQTT_TOPIC_RESPONSE)
    print(f"Subscribed to response topic: {MQTT_TOPIC_RESPONSE}")

def on_message(client, userdata, msg):
    try:
        response = json.loads(msg.payload.decode())
        print(f"Received response: {response}")
        
        message_id = response.get('id')
        status = response.get('status')
        
        if not message_id or not status:
            print("Invalid response format, missing id or status")
            return
        
        with response_lock:
            if message_id in response_events:
                response_data[message_id] = response
                if status == "processing" or status.startswith("received"):
                    response_events[message_id].set()
                    print(f"Notifying waiters for command {message_id} with status: {status}")
            else:
                print(f"Response for unknown or already completed command {message_id}: {status}")
                
    except json.JSONDecodeError:
        print("Invalid JSON in response")
    except Exception as e:
        print(f"Error processing response: {e}")

def wait_for_response(message_id, timeout=MAX_WAIT_TIME):
    start_time = time.time()
    
    with response_lock:
        if message_id in response_data:
            response = response_data[message_id]
            del response_data[message_id]
            if message_id in response_events:
                del response_events[message_id]
            return response
        
        event = Event()
        response_events[message_id] = event
    
    event_set = event.wait(timeout)
    
    with response_lock:
        if message_id in response_events:
            del response_events[message_id]
        
        if event_set and message_id in response_data:
            response = response_data[message_id]
            del response_data[message_id]
            return response
        
    return None

def vibrate(left_duration: float, right_duration: float):
    message_id = str(uuid.uuid4())
    
    payload = {
        "message_id": message_id,
        "left_duration": round(left_duration, 2),
        "right_duration": round(right_duration, 2),
        "timestamp": time.time()
    }
    
    message = json.dumps(payload)
    client_publish.publish(MQTT_TOPIC_PUBLISH, message)
    print(f"Published: {message}")
    
    return message_id, payload

@app.route('/vibrate', methods=['POST'])
def vibrate_endpoint():
    try:
        data = request.get_json()
        
        if 'left_duration' not in data or 'right_duration' not in data:
            return jsonify({
                'error': 'Missing required parameters. Please provide left_duration and right_duration'
            }), 400
            
        try:
            left_duration = float(data['left_duration'])
            right_duration = float(data['right_duration'])
            
            message_id, payload = vibrate(left_duration, right_duration)
            
            response = wait_for_response(message_id)
            
            if response:
                status = response.get('status', 'unknown')
                
                return jsonify({
                    'status': status,
                    'message_id': message_id,
                    'data': payload,
                    'response': response
                }), 200
            else:
                return jsonify({
                    'status': 'timeout',
                    'message': 'Timed out waiting for motor controller response',
                    'message_id': message_id,
                    'data': payload
                }), 202
            
        except ValueError:
            return jsonify({
                'error': 'Invalid parameter values. Duration must be a number'
            }), 400
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to process request: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'mqtt_topic_publish': MQTT_TOPIC_PUBLISH,
        'mqtt_topic_response': MQTT_TOPIC_RESPONSE,
        'mqtt_broker_local': MQTT_BROKER_LOCAL,
        'mqtt_broker_response': MQTT_BROKER_RESPONSE,
        'pending_responses': len(response_events)
    }), 200

def cleanup_expired_events():
    while True:
        time.sleep(60)
        current_time = time.time()
        with response_lock:
            expired = [mid for mid in response_events if current_time - response_events.get(mid, current_time) > MAX_WAIT_TIME * 2]
            for mid in expired:
                if mid in response_events:
                    del response_events[mid]
                if mid in response_data:
                    del response_data[mid]
            if expired:
                print(f"Cleaned up {len(expired)} expired events")

cleanup_thread = threading.Thread(target=cleanup_expired_events, daemon=True)
cleanup_thread.start()

client_subscribe.on_connect = on_connect_subscribe
client_subscribe.on_message = on_message

print(f"Connecting to response MQTT broker at {MQTT_BROKER_RESPONSE}:{MQTT_PORT}")
client_subscribe.connect(MQTT_BROKER_RESPONSE, MQTT_PORT, 60)
client_subscribe.loop_start()

print(f"Connecting to local MQTT broker at {MQTT_BROKER_LOCAL}:{MQTT_PORT}")
client_publish.connect(MQTT_BROKER_LOCAL, MQTT_PORT, 60)
client_publish.loop_start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)