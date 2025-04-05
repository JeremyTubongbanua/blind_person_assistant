#!/usr/bin/env python3
"""
This script subscribes to the "pi4/gyro" MQTT topic and prints incoming messages.
Use the --host argument to specify the MQTT broker host (either 192.168.8.220 or 127.0.0.1).
"""

import argparse
import paho.mqtt.client as mqtt

# Define default topic and available hosts
DEFAULT_TOPIC = "pi4/gyro"
AVAILABLE_HOSTS = ["192.168.8.220", "127.0.0.1"]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe(DEFAULT_TOPIC)
    else:
        print("Failed to connect. Return code", rc)

def on_message(client, userdata, msg):
    print(f"Topic: {msg.topic} | Message: {msg.payload.decode()}")

def main():
    parser = argparse.ArgumentParser(description="MQTT Subscriber to test gyro publisher")
    parser.add_argument(
        "--host", 
        type=str, 
        required=False, 
        default="127.0.0.1", 
        choices=AVAILABLE_HOSTS,
        help="MQTT Broker host. Choices: 192.168.8.220 or 127.0.0.1 (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=False,
        default=1883,
        help="MQTT Broker port (default: 1883)"
    )
    args = parser.parse_args()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print(f"Connecting to {args.host}:{args.port}...")
        client.connect(args.host, args.port, 60)
    except Exception as e:
        print("Could not connect to MQTT Broker:", e)
        return

    # Blocking loop to the client loop forever
    client.loop_forever()

if __name__ == "__main__":
    main()
