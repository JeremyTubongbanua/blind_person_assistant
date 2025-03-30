from flask import Flask, jsonify
import requests
import subprocess
import os
from functools import wraps

STREAM_URL = 'http://localhost:8005/video_stream'
SERVICE_NAME = 'camera-stream.service'
REQUEST_TIMEOUT = 1
API_PORT = 8010
API_HOST = '0.0.0.0'

app = Flask(__name__)

def check_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if os.geteuid() != 0:
            return jsonify({"error": "This API must be run as root to control systemd services"}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/status', methods=['GET'])
def check_status():
    try:
        response = requests.head(STREAM_URL, timeout=REQUEST_TIMEOUT, stream=True)
        
        service_status = subprocess.run(['systemctl', 'is-active', SERVICE_NAME], 
                                      capture_output=True, text=True)
        
        return jsonify({
            "status": "online" if response.status_code < 400 else "error",
            "code": response.status_code,
            "service_status": service_status.stdout.strip(),
            "port_accessible": True
        })
    except requests.exceptions.RequestException:
        service_status = subprocess.run(['systemctl', 'is-active', SERVICE_NAME], 
                                      capture_output=True, text=True)
        
        return jsonify({
            "status": "offline",
            "detail": "Unable to connect to video stream",
            "service_status": service_status.stdout.strip(),
            "port_accessible": False
        })
        
@app.route('/start', methods=['POST'])
@check_auth
def start_service():
    result = subprocess.run(['systemctl', 'start', SERVICE_NAME], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        return jsonify({"status": "success", "message": "Camera stream service started"}), 200
    else:
        return jsonify({"status": "error", "message": result.stderr}), 500

@app.route('/stop', methods=['POST'])
@check_auth
def stop_service():
    result = subprocess.run(['systemctl', 'stop', SERVICE_NAME], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        return jsonify({"status": "success", "message": "Camera stream service stopped"}), 200
    else:
        return jsonify({"status": "error", "message": result.stderr}), 500

@app.route('/restart', methods=['POST'])
@check_auth
def restart_service():
    result = subprocess.run(['systemctl', 'restart', SERVICE_NAME], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        return jsonify({"status": "success", "message": "Camera stream service restarted"}), 200
    else:
        return jsonify({"status": "error", "message": result.stderr}), 500

if __name__ == '__main__':
    app.run(host=API_HOST, port=API_PORT)
