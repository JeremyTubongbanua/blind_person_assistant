#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import signal
import sys

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "pi4/detections"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        print(f"Subscribing to topic: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Connection failed with error code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        print(f"Received message on {msg.topic}:")
        
        # Try to parse as JSON
        try:
            data = json.loads(payload)
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            # Not JSON, just print the raw message
            print(payload)
        
        print("-" * 40)
    except Exception as e:
        print(f"Error processing message: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection with code {rc}")
    else:
        print("Disconnected from broker")

def signal_handler(sig, frame):
    print("\nExiting...")
    client.disconnect()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize MQTT client
    client = mqtt.Client()
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Connect to broker
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Error connecting to broker: {e}")
        sys.exit(1)
    
    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
    print("Press Ctrl+C to exit")
    
    # Start the loop
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nExiting...")
        client.disconnect()