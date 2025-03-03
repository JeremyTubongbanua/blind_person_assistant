import json
import uuid
import threading
import time
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC_PUBLISH = "pi4/vibration_motor_controller"
MQTT_TOPIC_RESPONSE = "pi2/vibration_motor_response" 

app = Flask(__name__)

pending_commands = {}
commands_lock = threading.Lock()
MAX_WAIT_TIME = 30

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to MQTT broker with result code: {rc}")
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
            
        with commands_lock:
            if message_id in pending_commands:
                pending_commands[message_id] = status
                print(f"Updated command {message_id} status to {status}")
            else:
                print(f"Received status update for unknown command: {message_id}")
                
    except json.JSONDecodeError:
        print("Invalid JSON in response")
    except Exception as e:
        print(f"Error processing response: {e}")

def vibrate(left_duration: float, right_duration: float):
    message_id = str(uuid.uuid4())
    
    payload = {
        "message_id": message_id,
        "left_duration": round(left_duration, 2),
        "right_duration": round(right_duration, 2)
    }
    
    with commands_lock:
        pending_commands[message_id] = "sending"
    
    message = json.dumps(payload)
    client.publish(MQTT_TOPIC_PUBLISH, message)
    print(f"Published: {message}")
    
    return message_id, payload

def wait_for_completion(message_id, timeout=MAX_WAIT_TIME):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        with commands_lock:
            if message_id in pending_commands:
                status = pending_commands[message_id]
                if status == "complete":
                    del pending_commands[message_id]
                    return True, status
            else:
                return False, "unknown_command"
                
        time.sleep(0.1)
    
    with commands_lock:
        if message_id in pending_commands:
            status = pending_commands[message_id]
            del pending_commands[message_id]
        else:
            status = "unknown"
            
    return False, status

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
            
            success, status = wait_for_completion(message_id)
            
            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Vibration command completed',
                    'message_id': message_id,
                    'data': payload
                }), 200
            else:
                return jsonify({
                    'status': 'timeout',
                    'message': f'Vibration command sent but completion not confirmed. Last status: {status}',
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
        'mqtt_topic': MQTT_TOPIC_PUBLISH,
        'response_topic': MQTT_TOPIC_RESPONSE,
        'pending_commands': len(pending_commands)
    }), 200

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)