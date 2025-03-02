import json
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC = "pi4/vibration_motor_controller"

app = Flask(__name__)

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

def vibrate(left_duration: float, right_duration: float):
    payload = {
        "left_duration": round(left_duration, 2),
        "right_duration": round(right_duration, 2)
    }
    
    message = json.dumps(payload)
    client.publish(MQTT_TOPIC, message)
    print(f"Published: {message}")
    
    return payload

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
            
            result = vibrate(left_duration, right_duration)
            return jsonify({
                'status': 'success',
                'message': 'Vibration command sent',
                'data': result
            }), 200
            
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
        'mqtt_topic': MQTT_TOPIC
    }), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
