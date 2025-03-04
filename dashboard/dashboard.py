from flask import Flask, render_template, request, jsonify
import paho.mqtt.client as mqtt
import json
import threading
import time
import requests
from flask_socketio import SocketIO
import os

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
socketio = SocketIO(app, cors_allowed_origins="*")

RPI2_BROKER = "192.168.2.219"
RPI4_BROKER = "192.168.2.220"
MQTT_PORT = 1883

RPI2_TOPICS = {
    "button_state": "pi2/button_state",
    "gyro": "pi2/gyro",
    "vibration_motor_response": "pi2/vibration_motor_response"
}

RPI4_TOPICS = {
    "detections": "pi4/detections",
    "gyro": "pi4/gyro",
    "vibration_motor_controller": "pi4/vibration_motor_controller"
}

last_messages = {
    "Cane Button State": None,
    "Gyro": None,
    "Vibration Motor Response": None,
    "Camera Detections": None,
    "Headset Gyro": None,
    "Headset Vibration Motor Controller": None
}

rpi2_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
rpi4_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_threads = []

def on_rpi2_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        
        if topic == RPI2_TOPICS["button_state"]:
            last_messages["Cane Button State"] = payload
            socketio.emit('mqtt_update', {'topic': 'Cane Button State', 'payload': payload})
        
        elif topic == RPI2_TOPICS["gyro"]:
            last_messages["Gyro"] = payload
            socketio.emit('mqtt_update', {'topic': 'Gyro', 'payload': payload})
        
        elif topic == RPI2_TOPICS["vibration_motor_response"]:
            last_messages["Vibration Motor Response"] = payload
            socketio.emit('mqtt_update', {'topic': 'Vibration Motor Response', 'payload': payload})
    
    except Exception as e:
        print(f"Error processing rpi2 message from {topic}: {e}")

def on_rpi4_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        
        if topic == RPI4_TOPICS["gyro"]:
            last_messages["Headset Gyro"] = payload
            socketio.emit('mqtt_update', {'topic': 'Headset Gyro', 'payload': payload})
        
        elif topic == RPI4_TOPICS["vibration_motor_controller"]:
            last_messages["Headset Vibration Motor Controller"] = payload
            socketio.emit('mqtt_update', {'topic': 'Headset Vibration Motor Controller', 'payload': payload})
    
        elif topic == RPI4_TOPICS["detections"]:
            last_messages["Camera Detections"] = payload
            socketio.emit('mqtt_update', {'topic': 'Camera Detections', 'payload': payload})

    except Exception as e:
        print(f"Error processing rpi4 message from {topic}: {e}")

def stop_mqtt_clients():
    global mqtt_threads
    
    print("Stopping MQTT clients...")
    try:
        rpi2_client.disconnect()
    except Exception as e:
        print(f"Error disconnecting RPI2 client: {e}")
        
    try:
        rpi4_client.disconnect()
    except Exception as e:
        print(f"Error disconnecting RPI4 client: {e}")
    
    # Wait for threads to terminate (with timeout)
    for thread in mqtt_threads:
        if thread.is_alive():
            thread.join(timeout=2)
    
    mqtt_threads = []
    print("MQTT clients stopped")

def setup_mqtt():
    global mqtt_threads
    
    # First stop existing connections
    stop_mqtt_clients()
    
    # Reset connection status for UI
    socketio.emit('mqtt_connection_status', {'status': 'connecting'})
    
    # Set up RPI2 client
    rpi2_client.on_message = on_rpi2_message
    rpi2_connected = False
    try:
        rpi2_client.connect(RPI2_BROKER, MQTT_PORT, 60)
        
        for topic in RPI2_TOPICS.values():
            rpi2_client.subscribe(topic)
            print(f"Subscribed to {topic} on {RPI2_BROKER}")
        rpi2_connected = True
    except Exception as e:
        print(f"Error connecting to {RPI2_BROKER}: {e}")
    
    # Set up RPI4 client
    rpi4_client.on_message = on_rpi4_message
    rpi4_connected = False
    try:
        rpi4_client.connect(RPI4_BROKER, MQTT_PORT, 60)
        
        rpi4_client.subscribe(RPI4_TOPICS["gyro"])
        rpi4_client.subscribe(RPI4_TOPICS["vibration_motor_controller"])
        rpi4_client.subscribe(RPI4_TOPICS["detections"])
        print(f"Subscribed to topics on {RPI4_BROKER}")
        rpi4_connected = True
    except Exception as e:
        print(f"Error connecting to {RPI4_BROKER}: {e}")
    
    # Start client loops in new threads
    if rpi2_connected:
        rpi2_thread = threading.Thread(target=rpi2_client_loop, daemon=True)
        rpi2_thread.start()
        mqtt_threads.append(rpi2_thread)
    
    if rpi4_connected:
        rpi4_thread = threading.Thread(target=rpi4_client_loop, daemon=True)
        rpi4_thread.start()
        mqtt_threads.append(rpi4_thread)
    
    # Notify frontend of connection status
    connection_status = {
        'rpi2_connected': rpi2_connected,
        'rpi4_connected': rpi4_connected,
        'status': 'connected' if (rpi2_connected or rpi4_connected) else 'failed'
    }
    socketio.emit('mqtt_connection_status', connection_status)
    
    return connection_status

def rpi2_client_loop():
    try:
        rpi2_client.loop_forever()
    except Exception as e:
        print(f"RPI2 MQTT loop error: {e}")
        socketio.emit('mqtt_connection_status', {'rpi2_connected': False})

def rpi4_client_loop():
    try:
        rpi4_client.loop_forever()
    except Exception as e:
        print(f"RPI4 MQTT loop error: {e}")
        socketio.emit('mqtt_connection_status', {'rpi4_connected': False})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vibrate', methods=['POST'])
def vibrate():
    try:
        data = request.get_json()
        response = requests.post(
            "http://localhost:5000/vibrate",
            headers={"Content-Type": "application/json"},
            json=data
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_data')
def get_all_data():
    return jsonify(last_messages)

@app.route('/refresh_mqtt', methods=['POST'])
def refresh_mqtt():
    try:
        connection_status = setup_mqtt()
        return jsonify({"status": "success", "connection": connection_status}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    setup_mqtt()
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
