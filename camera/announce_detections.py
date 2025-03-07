#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import subprocess
import threading
from urllib.parse import quote

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC = "pi4/detections"
TTS_URL = "http://localhost:5001/tts"
ANNOUNCEMENT_INTERVAL = 5
VOICE_NAME = "en-us"
SPEECH_SPEED = "175"

latest_detections = None
last_announcement_time = 0
announcement_lock = threading.Lock()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global latest_detections
    try:
        data = json.loads(msg.payload.decode())
        with announcement_lock:
            latest_detections = data.get("detections", [])
            print(f"Received {len(latest_detections)} detections")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def announce_detections():
    global latest_detections, last_announcement_time
    
    while True:
        current_time = time.time()
        
        if current_time - last_announcement_time >= ANNOUNCEMENT_INTERVAL:
            with announcement_lock:
                detections_to_announce = latest_detections
                latest_detections = None
            
            if detections_to_announce and len(detections_to_announce) > 0:
                # Count occurrences of each label
                label_counts = {}
                for detection in detections_to_announce:
                    label = detection.get("label", "unknown")
                    label_counts[label] = label_counts.get(label, 0) + 1
                
                # Build a simple announcement
                announcement = "Detected "
                label_phrases = []
                for label, count in label_counts.items():
                    label_phrases.append(f"{count} {label}{'s' if count > 1 else ''}")
                
                announcement += ", ".join(label_phrases)
                
                try:
                    encoded_text = quote(announcement)
                    curl_command = f'curl "{TTS_URL}?text={encoded_text}&speed={SPEECH_SPEED}&voice_name={VOICE_NAME}"'
                    subprocess.run(curl_command, shell=True)
                    print(f"Announced: {announcement}")
                except Exception as e:
                    print(f"Error making TTS request: {e}")
            
            last_announcement_time = current_time
        
        time.sleep(0.5)

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        client.loop_start()
        
        announcement_thread = threading.Thread(target=announce_detections, daemon=True)
        announcement_thread.start()
        
        print("Detection announcer started. Press Ctrl+C to exit.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()