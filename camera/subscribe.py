#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Subscribe to DepthAI detection MQTT messages')
parser.add_argument('--broker', default='raspberrypi4.local', help='MQTT broker address')
parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
parser.add_argument('--topic', default='depthai/detections', help='MQTT topic to subscribe to')
args = parser.parse_args()

# Callback when connection is established
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {args.broker}:{args.port}")
        # Subscribe to the topic
        client.subscribe(args.topic)
        print(f"Subscribed to topic: {args.topic}")
    else:
        print(f"Failed to connect to MQTT broker with return code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    try:
        # Parse the JSON payload
        payload = json.loads(msg.payload.decode())
        
        # Print timestamp
        print(f"\n--- New Detections at {time.strftime('%H:%M:%S')} ---")
        
        # Check if there are any detections
        if "detections" in payload and payload["detections"]:
            for i, detection in enumerate(payload["detections"]):
                print(f"Detection {i+1}:")
                print(f"  Label: {detection['label']}")
                print(f"  Confidence: {detection['confidence']:.2f}")
                print(f"  Bounding Box: x1={detection['bbox']['x1']}, y1={detection['bbox']['y1']}, "
                      f"x2={detection['bbox']['x2']}, y2={detection['bbox']['y2']}")
                
                if "distance" in detection:
                    print(f"  Distance: {detection['distance']:.2f}m")
                print("")
        else:
            print("No detections in this message")
    
    except json.JSONDecodeError:
        print(f"Received message is not valid JSON: {msg.payload.decode()}")
    except Exception as e:
        print(f"Error processing message: {e}")

# Create MQTT client
client = mqtt.Client()

# Set callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
print(f"Connecting to MQTT broker at {args.broker}:{args.port}...")
client.connect(args.broker, args.port, 60)

# Start the loop
try:
    print("Waiting for messages. Press Ctrl+C to exit.")
    client.loop_forever()
except KeyboardInterrupt:
    print("\nExiting...")
    client.disconnect()