from flask import Flask, render_template, jsonify
import paho.mqtt.client as mqtt
import json
import math
import time

app = Flask(__name__)

last_timestamp = 0
first_message = True
gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}

# Add calibration values
gyro_calibration = {"x": 0, "y": 0, "z": 0}
calibration_samples = 0
is_calibrating = True
CALIBRATION_SAMPLES_NEEDED = 10

# Add drift compensation
YAW_DRIFT_COMPENSATION = 0.98  # Damping factor for yaw integration

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
    global sensor_data, last_timestamp, gyro_integrated, first_message
    global gyro_calibration, calibration_samples, is_calibrating
    
    try:
        data = json.loads(msg.payload.decode())
        
        gyro_x = data.get("gyro", {}).get("x", 0)
        gyro_y = data.get("gyro", {}).get("y", 0)
        gyro_z = data.get("gyro", {}).get("z", 0)
        
        current_timestamp = data.get("timestamp", 0)
        
        if is_calibrating and calibration_samples < CALIBRATION_SAMPLES_NEEDED:
            gyro_calibration["x"] += gyro_x
            gyro_calibration["y"] += gyro_y
            gyro_calibration["z"] += gyro_z
            calibration_samples += 1
            
            if calibration_samples == CALIBRATION_SAMPLES_NEEDED:
                gyro_calibration["x"] /= CALIBRATION_SAMPLES_NEEDED
                gyro_calibration["y"] /= CALIBRATION_SAMPLES_NEEDED
                gyro_calibration["z"] /= CALIBRATION_SAMPLES_NEEDED
                is_calibrating = False
                print(f"Calibration complete: {gyro_calibration}")
            return
        
        gyro_x -= gyro_calibration["x"]
        gyro_y -= gyro_calibration["y"]
        gyro_z -= gyro_calibration["z"]
        
        noise_threshold = 0.03
        if abs(gyro_x) < noise_threshold: gyro_x = 0
        if abs(gyro_y) < noise_threshold: gyro_y = 0
        if abs(gyro_z) < noise_threshold: gyro_z = 0
        
        if first_message:
            gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}
            first_message = False
            last_timestamp = current_timestamp
            
            accel_x = data.get("accel", {}).get("x", 0)
            accel_y = data.get("accel", {}).get("y", 0)
            accel_z = data.get("accel", {}).get("z", 0)
            
            roll = math.degrees(math.atan2(accel_y, accel_z))
            pitch = math.degrees(math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)))
            yaw = 0  # Can't determine yaw from accelerometer alone
            
            gyro_integrated["roll"] = roll
            gyro_integrated["pitch"] = pitch
        elif last_timestamp > 0:
            dt = current_timestamp - last_timestamp
            
            accel_x = data.get("accel", {}).get("x", 0)
            accel_y = data.get("accel", {}).get("y", 0)
            accel_z = data.get("accel", {}).get("z", 0)
            
            accel_roll = math.degrees(math.atan2(accel_y, accel_z))
            accel_pitch = math.degrees(math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)))
            
            gyro_integrated["roll"] += gyro_x * dt
            gyro_integrated["pitch"] += gyro_y * dt
            gyro_integrated["yaw"] += gyro_z * dt * YAW_DRIFT_COMPENSATION
            
            alpha = 0.96  # Adjust this value (0.9-0.98) to balance gyro and accel
            gyro_integrated["roll"] = alpha * gyro_integrated["roll"] + (1 - alpha) * accel_roll
            gyro_integrated["pitch"] = alpha * gyro_integrated["pitch"] + (1 - alpha) * accel_pitch
            
            if gyro_integrated["yaw"] > 180:
                gyro_integrated["yaw"] -= 360
            elif gyro_integrated["yaw"] < -180:
                gyro_integrated["yaw"] += 360
        
        last_timestamp = current_timestamp
        
        roll = max(min(gyro_integrated["roll"], 180), -180)+90
        pitch = max(min(gyro_integrated["pitch"], 180), -180)
        yaw = -max(min(gyro_integrated["yaw"], 180), -180)
        
        sensor_data = {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "accel_x": data.get("accel", {}).get("x", 0),
            "accel_y": data.get("accel", {}).get("y", 0),
            "accel_z": data.get("accel", {}).get("z", 0),
            "timestamp": current_timestamp,
            "is_calibrated": not is_calibrating
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
    global gyro_integrated, last_timestamp, first_message
    global gyro_calibration, calibration_samples, is_calibrating
    
    gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}
    last_timestamp = 0
    first_message = True
    
    # Recalibrate
    gyro_calibration = {"x": 0, "y": 0, "z": 0}
    calibration_samples = 0
    is_calibrating = True
    
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