from flask import Flask, render_template, request, jsonify
import paho.mqtt.client as mqtt
import json
import threading
import time
import requests
from flask_socketio import SocketIO
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 8080
FLASK_DEBUG = False
RPI2_BROKER = "192.168.2.219"
RPI4_BROKER = "192.168.2.220"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

RPI2_TOPICS = {
    "button_state": "pi2/button_state",
    "gyro": "pi2/gyro",
    "vibration_motor_response": "pi2/vibration_motor_response",
    "pitch_yaw_roll": "pi2/pitch_yaw_roll"
}

RPI4_TOPICS = {
    "gyro": "pi4/gyro",
    "vibration_motor_controller": "pi4/vibration_motor_controller",
    "pitch_yaw_roll": "pi4/pitch_yaw_roll",
    "detections": "pi4/detections",
    "detection_image": "pi4/detection_image",
    "depth_map": "pi4/depth_map",
    "menu": "pi4/menu",
    "menu_logs": "pi4/menu_logs"
}

MESSAGE_CATEGORIES = {
    "CANE_BUTTON_STATE": "Cane Button State",
    "GYRO": "Gyro",
    "VIBRATION_MOTOR_RESPONSE": "Vibration Motor Response",
    "CAMERA_DETECTIONS": "Camera Detections",
    "HEADSET_GYRO": "Headset Gyro",
    "HEADSET_VIBRATION_MOTOR_CONTROLLER": "Headset Vibration Motor Controller",
    "PITCH_YAW_ROLL": "Pitch Yaw Roll",
    "MENU": "Menu",
    "MENU_LOGS": "Menu Logs"
}

CAMERA_CONTROL_API_URL = "http://localhost:8010"
VIBRATION_API_URL = "http://localhost:5000/vibrate"
DETECTION_API_URL = "http://localhost:8005/detections"
AUDIO_API_BASE_URL = "http://localhost:5001"
PLAY_AUDIO_ENDPOINT = f"{AUDIO_API_BASE_URL}/play_file"
SET_VOLUME_ENDPOINT = f"{AUDIO_API_BASE_URL}/set_volume"
GET_VOLUME_ENDPOINT = f"{AUDIO_API_BASE_URL}/get_volume"
TTS_ENDPOINT = f"{AUDIO_API_BASE_URL}/tts"
HEADSET_CALIBRATION_ENDPOINT = f"http://{RPI4_BROKER}:5002/calibrate"
HEADSET_ZERO_ENDPOINT = f"http://{RPI4_BROKER}:5002/zero"
CANE_CALIBRATION_ENDPOINT = f"http://{RPI2_BROKER}:5002/calibrate"
CANE_ZERO_ENDPOINT = f"http://{RPI2_BROKER}:5002/zero"
MQTT_API_URL = "http://localhost:8080/mqtt_service"
CAMERA_CONTROL_START_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/start"
CAMERA_CONTROL_STOP_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/stop"
CAMERA_CONTROL_STATUS_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/status"

DEFAULT_TTS_SPEED = 125
DEFAULT_TTS_VOICE = "en-us"

SOCKETIO_MQTT_UPDATE = 'mqtt_update'
SOCKETIO_MQTT_CONNECTION_STATUS = 'mqtt_connection_status'
SOCKETIO_MQTT_MESSAGE = 'mqtt_message'

app = Flask(__name__, template_folder=TEMPLATE_DIR)
socketio = SocketIO(app, cors_allowed_origins="*")

last_messages = {
    MESSAGE_CATEGORIES["CANE_BUTTON_STATE"]: None,
    MESSAGE_CATEGORIES["GYRO"]: None,
    MESSAGE_CATEGORIES["VIBRATION_MOTOR_RESPONSE"]: None,
    MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]: None,
    MESSAGE_CATEGORIES["HEADSET_GYRO"]: None,
    MESSAGE_CATEGORIES["HEADSET_VIBRATION_MOTOR_CONTROLLER"]: None,
    MESSAGE_CATEGORIES["PITCH_YAW_ROLL"]: None
}

rpi2_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
rpi4_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_threads = []

def on_rpi2_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        
        if topic == RPI2_TOPICS["button_state"]:
            last_messages[MESSAGE_CATEGORIES["CANE_BUTTON_STATE"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["CANE_BUTTON_STATE"], 'payload': payload})
        
        elif topic == RPI2_TOPICS["gyro"]:
            last_messages[MESSAGE_CATEGORIES["GYRO"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["GYRO"], 'payload': payload})
        
        elif topic == RPI2_TOPICS["vibration_motor_response"]:
            last_messages[MESSAGE_CATEGORIES["VIBRATION_MOTOR_RESPONSE"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["VIBRATION_MOTOR_RESPONSE"], 'payload': payload})
    
        elif topic == RPI2_TOPICS["pitch_yaw_roll"]:
            last_messages[MESSAGE_CATEGORIES["PITCH_YAW_ROLL"]] = payload
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
    
    except Exception as e:
        print(f"Error processing rpi2 message from {topic}: {e}")

def on_rpi4_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        
        if topic == RPI4_TOPICS["gyro"]:
            last_messages[MESSAGE_CATEGORIES["HEADSET_GYRO"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["HEADSET_GYRO"], 'payload': payload})
        
        elif topic == RPI4_TOPICS["vibration_motor_controller"]:
            last_messages[MESSAGE_CATEGORIES["HEADSET_VIBRATION_MOTOR_CONTROLLER"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["HEADSET_VIBRATION_MOTOR_CONTROLLER"], 'payload': payload})
        
        elif topic == RPI4_TOPICS["pitch_yaw_roll"]:
            last_messages[MESSAGE_CATEGORIES["PITCH_YAW_ROLL"]] = payload
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
            
        elif topic == RPI4_TOPICS["detections"]:
            if last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] is None:
                last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] = {}
            last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]]["detections"] = payload
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': payload})
            print(f'emitted: {topic} {payload}')
            
        elif topic == RPI4_TOPICS["detection_image"]:
            if last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] is None:
                last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] = {}
            last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]]["detection_image"] = payload
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
            
        elif topic == RPI4_TOPICS["depth_map"]:
            if last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] is None:
                last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] = {}
            last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]]["depth_map"] = payload
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
        
        elif topic == RPI4_TOPICS["menu"]:
            last_messages[MESSAGE_CATEGORIES["MENU"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["MENU"], 'payload': payload})
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
            
        elif topic == RPI4_TOPICS["menu_logs"]:
            last_messages[MESSAGE_CATEGORIES["MENU_LOGS"]] = payload
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["MENU_LOGS"], 'payload': payload})
            socketio.emit(SOCKETIO_MQTT_MESSAGE, {'topic': topic, 'payload': msg.payload.decode()})
    
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
    
    for thread in mqtt_threads:
        if thread.is_alive():
            thread.join(timeout=2)
    
    mqtt_threads = []
    print("MQTT clients stopped")

def setup_mqtt():
    global mqtt_threads
    
    stop_mqtt_clients()
    
    socketio.emit(SOCKETIO_MQTT_CONNECTION_STATUS, {'status': 'connecting'})
    
    rpi2_client.on_message = on_rpi2_message
    rpi2_connected = False
    try:
        rpi2_client.connect(RPI2_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        
        for topic in RPI2_TOPICS.values():
            rpi2_client.subscribe(topic)
            print(f"Subscribed to {topic} on {RPI2_BROKER}")
        rpi2_connected = True
    except Exception as e:
        print(f"Error connecting to {RPI2_BROKER}: {e}")
    
    rpi4_client.on_message = on_rpi4_message
    rpi4_connected = False
    try:
        rpi4_client.connect(RPI4_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        
        for topic in RPI4_TOPICS.values():
            rpi4_client.subscribe(topic)
            print(f"Subscribed to {topic} on {RPI4_BROKER}")
        rpi4_connected = True
    except Exception as e:
        print(f"Error connecting to {RPI4_BROKER}: {e}")
    
    if rpi2_connected:
        rpi2_thread = threading.Thread(target=rpi2_client_loop, daemon=True)
        rpi2_thread.start()
        mqtt_threads.append(rpi2_thread)
    
    if rpi4_connected:
        rpi4_thread = threading.Thread(target=rpi4_client_loop, daemon=True)
        rpi4_thread.start()
        mqtt_threads.append(rpi4_thread)
    
    connection_status = {
        'rpi2_connected': rpi2_connected,
        'rpi4_connected': rpi4_connected,
        'status': 'connected' if (rpi2_connected or rpi4_connected) else 'failed'
    }
    socketio.emit(SOCKETIO_MQTT_CONNECTION_STATUS, connection_status)
    
    return connection_status

def rpi2_client_loop():
    try:
        rpi2_client.loop_forever()
    except Exception as e:
        print(f"RPI2 MQTT loop error: {e}")
        socketio.emit(SOCKETIO_MQTT_CONNECTION_STATUS, {'rpi2_connected': False})

def rpi4_client_loop():
    try:
        rpi4_client.loop_forever()
    except Exception as e:
        print(f"RPI4 MQTT loop error: {e}")
        socketio.emit(SOCKETIO_MQTT_CONNECTION_STATUS, {'rpi4_connected': False})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vibrate', methods=['POST'])
def vibrate():
    try:
        data = request.get_json()
        response = requests.post(
            VIBRATION_API_URL,
            headers={"Content-Type": "application/json"},
            json=data
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/run_detection', methods=['GET'])
def run_detection():
    try:
        response = requests.get(DETECTION_API_URL)
        detection_data = response.json()
        
        if 'status' in detection_data and detection_data['status'] == 'ok':
            last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] = detection_data
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["CAMERA_DETECTIONS"], 'payload': detection_data})
        
        return jsonify(detection_data), 200
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

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

@app.route('/play_audio', methods=['POST'])
def play_audio():
    try:
        data = request.get_json()
        file_name = data.get('file')
        
        response = requests.get(
            f"{PLAY_AUDIO_ENDPOINT}?file={file_name}"
        )
        return jsonify({"status": "success", "message": f"Playing {file_name}"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/set_volume', methods=['POST'])
def set_volume():
    try:
        data = request.get_json()
        volume = data.get('volume')
        
        response = requests.get(
            f"{SET_VOLUME_ENDPOINT}?volume={volume}"
        )
        return jsonify({"status": "success", "message": f"Volume set to {volume}%"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/get_volume', methods=['GET'])
def get_volume():
    try:
        response = requests.get(GET_VOLUME_ENDPOINT)
        volume_data = response.json()
        return jsonify(volume_data), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get('text')
        speed = data.get('speed', DEFAULT_TTS_SPEED)
        voice_name = data.get('voice_name', DEFAULT_TTS_VOICE)
        
        response = requests.get(
            f"{TTS_ENDPOINT}?text={text}&speed={speed}&voice_name={voice_name}"
        )
        return jsonify({"status": "success", "message": "Speech played successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/calibrate_headset_gyro', methods=['POST'])
def calibrate_headset_gyro():
    try:
        response = requests.post(HEADSET_CALIBRATION_ENDPOINT)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/zero_headset_gyro', methods=['POST'])
def zero_headset_gyro():
    try:
        response = requests.post(f"{HEADSET_ZERO_ENDPOINT}")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/calibrate_cane_gyro', methods=['POST'])
def calibrate_cane_gyro():
    try:
        response = requests.post(CANE_CALIBRATION_ENDPOINT)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/zero_cane_gyro', methods=['POST'])
def zero_cane_gyro():
    try:
        response = requests.post(f"{CANE_ZERO_ENDPOINT}")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/start_camera', methods=['POST'])
def start_camera():
    try:
        response = requests.post(CAMERA_CONTROL_START_API_ENDPOINT)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/stop_camera', methods=['POST'])
def stop_camera():
    try:
        response = requests.post(CAMERA_CONTROL_STOP_API_ENDPOINT)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/camera_status', methods=['GET'])
def camera_status():
    try:
        response = requests.get(CAMERA_CONTROL_STATUS_API_ENDPOINT)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/restart_camera', methods=['POST'])
def restart_camera():
    try:
        response = requests.post(f"{CAMERA_CONTROL_API_URL}/restart")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    setup_mqtt()
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, allow_unsafe_werkzeug=True)
