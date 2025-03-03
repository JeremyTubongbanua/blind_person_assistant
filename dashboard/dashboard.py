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

def setup_mqtt():
    rpi2_client.on_message = on_rpi2_message
    try:
        rpi2_client.connect(RPI2_BROKER, MQTT_PORT, 60)
        
        for topic in RPI2_TOPICS.values():
            rpi2_client.subscribe(topic)
            print(f"Subscribed to {topic} on {RPI2_BROKER}")
    except Exception as e:
        print(f"Error connecting to {RPI2_BROKER}: {e}")
    
    rpi4_client.on_message = on_rpi4_message
    try:
        rpi4_client.connect(RPI4_BROKER, MQTT_PORT, 60)
        
        rpi4_client.subscribe(RPI4_TOPICS["gyro"])
        rpi4_client.subscribe(RPI4_TOPICS["vibration_motor_controller"])
        rpi4_client.subscribe(RPI4_TOPICS["detections"])
        print(f"Subscribed to topics on {RPI4_BROKER}")
    except Exception as e:
        print(f"Error connecting to {RPI4_BROKER}: {e}")
        
    threading.Thread(target=rpi2_client_loop, daemon=True).start()
    threading.Thread(target=rpi4_client_loop, daemon=True).start()

def rpi2_client_loop():
    try:
        rpi2_client.loop_forever()
    except Exception as e:
        print(f"RPI2 MQTT loop error: {e}")

def rpi4_client_loop():
    try:
        rpi4_client.loop_forever()
    except Exception as e:
        print(f"RPI4 MQTT loop error: {e}")

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

if __name__ == '__main__':
    setup_mqtt()
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
