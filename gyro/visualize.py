from flask import Flask, render_template, jsonify
import paho.mqtt.client as mqtt
import json
import math
import time

app = Flask(__name__)

last_timestamp = 0
gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}

sensor_data = {
    "roll": 0,
    "pitch": 0,
    "yaw": 0,
    "accel_x": 0,
    "accel_y": 0,
    "accel_z": 0,
    "timestamp": 0
}

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "pi4/gyro"

def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global sensor_data, last_timestamp, gyro_integrated
    try:
        data = json.loads(msg.payload.decode())
        
        gyro_x = data.get("gyro", {}).get("x", 0)
        gyro_y = data.get("gyro", {}).get("y", 0)
        gyro_z = data.get("gyro", {}).get("z", 0)
        
        current_timestamp = data.get("timestamp", 0)
        
        if last_timestamp > 0:
            dt = current_timestamp - last_timestamp
            
            gyro_integrated["roll"] += gyro_x * dt
            gyro_integrated["pitch"] += gyro_y * dt
            gyro_integrated["yaw"] += gyro_z * dt
            
            roll = gyro_integrated["roll"]
            pitch = gyro_integrated["pitch"]
            yaw = gyro_integrated["yaw"]
        else:
            roll = math.degrees(math.atan2(gyro_y, math.sqrt(gyro_x**2 + gyro_z**2)))
            pitch = math.degrees(math.atan2(gyro_x, math.sqrt(gyro_y**2 + gyro_z**2)))
            yaw = math.degrees(math.atan2(gyro_z, math.sqrt(gyro_x**2 + gyro_y**2)))
            
            gyro_integrated["roll"] = roll
            gyro_integrated["pitch"] = pitch
            gyro_integrated["yaw"] = yaw
        
        last_timestamp = current_timestamp
        
        roll = max(min(roll, 180), -180)
        pitch = max(min(pitch, 180), -180)
        yaw = max(min(yaw, 180), -180)
        
        sensor_data = {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "accel_x": data.get("accel", {}).get("x", 0),
            "accel_y": data.get("accel", {}).get("y", 0),
            "accel_z": data.get("accel", {}).get("z", 0),
            "timestamp": current_timestamp
        }
    except Exception as e:
        print(f"Error: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gyro_data')
def get_data():
    return jsonify(sensor_data)

@app.route('/reset')
def reset_integration():
    global gyro_integrated, last_timestamp
    gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}
    last_timestamp = 0
    return jsonify({"status": "reset"})

if __name__ == '__main__':
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        app.run(debug=True, host='0.0.0.0', port=5002)
    except KeyboardInterrupt:
        client.loop_stop()
    except Exception as e:
        app.run(debug=True, host='0.0.0.0', port=5002)