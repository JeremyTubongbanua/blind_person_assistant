#!/usr/bin/env python3

import time
import json
import smbus
import paho.mqtt.client as mqtt

class mpu6050:

    GRAVITIY_MS2 = 9.80665
    address = None
    bus = None

    ACCEL_SCALE_MODIFIER_2G = 16384.0
    ACCEL_SCALE_MODIFIER_4G = 8192.0
    ACCEL_SCALE_MODIFIER_8G = 4096.0
    ACCEL_SCALE_MODIFIER_16G = 2048.0

    GYRO_SCALE_MODIFIER_250DEG = 131.0
    GYRO_SCALE_MODIFIER_500DEG = 65.5
    GYRO_SCALE_MODIFIER_1000DEG = 32.8
    GYRO_SCALE_MODIFIER_2000DEG = 16.4

    ACCEL_RANGE_2G = 0x00
    ACCEL_RANGE_4G = 0x08
    ACCEL_RANGE_8G = 0x10
    ACCEL_RANGE_16G = 0x18

    GYRO_RANGE_250DEG = 0x00
    GYRO_RANGE_500DEG = 0x08
    GYRO_RANGE_1000DEG = 0x10
    GYRO_RANGE_2000DEG = 0x18

    PWR_MGMT_1   = 0x6B
    PWR_MGMT_2   = 0x6C

    ACCEL_XOUT0  = 0x3B
    ACCEL_YOUT0  = 0x3D
    ACCEL_ZOUT0  = 0x3F

    TEMP_OUT0    = 0x41

    GYRO_XOUT0   = 0x43
    GYRO_YOUT0   = 0x45
    GYRO_ZOUT0   = 0x47

    ACCEL_CONFIG = 0x1C
    GYRO_CONFIG  = 0x1B
    MPU_CONFIG   = 0x1A

    def __init__(self, address, bus=1):
        self.address = address
        self.bus = smbus.SMBus(bus)
        self.bus.write_byte_data(self.address, self.PWR_MGMT_1, 0x00)

    def read_i2c_word(self, register):
        high = self.bus.read_byte_data(self.address, register)
        low  = self.bus.read_byte_data(self.address, register + 1)
        value = (high << 8) + low
        if (value >= 0x8000):
            return -((65535 - value) + 1)
        else:
            return value

    def get_accel_data(self, g=False):
        x = self.read_i2c_word(self.ACCEL_XOUT0)
        y = self.read_i2c_word(self.ACCEL_YOUT0)
        z = self.read_i2c_word(self.ACCEL_ZOUT0)

        accel_range = self.bus.read_byte_data(self.address, self.ACCEL_CONFIG)
        if accel_range == self.ACCEL_RANGE_2G:
            accel_scale_modifier = self.ACCEL_SCALE_MODIFIER_2G
        elif accel_range == self.ACCEL_RANGE_4G:
            accel_scale_modifier = self.ACCEL_SCALE_MODIFIER_4G
        elif accel_range == self.ACCEL_RANGE_8G:
            accel_scale_modifier = self.ACCEL_SCALE_MODIFIER_8G
        elif accel_range == self.ACCEL_RANGE_16G:
            accel_scale_modifier = self.ACCEL_SCALE_MODIFIER_16G
        else:
            print("Unknown accel range, defaulting to 2G")
            accel_scale_modifier = self.ACCEL_SCALE_MODIFIER_2G

        x = x / accel_scale_modifier
        y = y / accel_scale_modifier
        z = z / accel_scale_modifier

        if g is True:
            return {'x': x, 'y': y, 'z': z}
        elif g is False:
            x = x * self.GRAVITIY_MS2
            y = y * self.GRAVITIY_MS2
            z = z * self.GRAVITIY_MS2
            return {'x': x, 'y': y, 'z': z}

    def get_gyro_data(self):
        x = self.read_i2c_word(self.GYRO_XOUT0)
        y = self.read_i2c_word(self.GYRO_YOUT0)
        z = self.read_i2c_word(self.GYRO_ZOUT0)

        gyro_range = self.bus.read_byte_data(self.address, self.GYRO_CONFIG)
        if gyro_range == self.GYRO_RANGE_250DEG:
            gyro_scale_modifier = self.GYRO_SCALE_MODIFIER_250DEG
        elif gyro_range == self.GYRO_RANGE_500DEG:
            gyro_scale_modifier = self.GYRO_SCALE_MODIFIER_500DEG
        elif gyro_range == self.GYRO_RANGE_1000DEG:
            gyro_scale_modifier = self.GYRO_SCALE_MODIFIER_1000DEG
        elif gyro_range == self.GYRO_RANGE_2000DEG:
            gyro_scale_modifier = self.GYRO_SCALE_MODIFIER_2000DEG
        else:
            print("Unknown gyro range, defaulting to 250deg/s")
            gyro_scale_modifier = self.GYRO_SCALE_MODIFIER_250DEG

        x = x / gyro_scale_modifier
        y = y / gyro_scale_modifier
        z = z / gyro_scale_modifier
        
        # temp_y = y
        # y = z
        # z = -temp_y
        
        return {'x': x, 'y': y, 'z': z}

MQTT_BROKER_HOST = "0.0.0.0"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC = "pi4/gyro"
PUBLISH_FREQUENCY = 0.05

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT Broker")
    else:
        print(f"Failed to connect, return code {rc}")

def main():
    sensor = mpu6050(0x68)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    except Exception as e:
        print("Could not connect to MQTT Broker:", e)
        return

    client.loop_start()

    try:
        while True:
            gyro_data = sensor.get_gyro_data()
            accel_data = sensor.get_accel_data()
            
            payload = {
                "gyro": {
                    "x": gyro_data["x"],
                    "y": gyro_data["y"],
                    "z": gyro_data["z"]
                },
                "accel": {
                    "x": accel_data["x"],
                    "y": accel_data["y"],
                    "z": accel_data["z"]
                },
                "timestamp": time.time()
            }
            
            payload_json = json.dumps(payload)
            client.publish(MQTT_TOPIC, payload_json)
            print(f"Published: gyro(x={gyro_data['x']:.2f}, y={gyro_data['y']:.2f}, z={gyro_data['z']:.2f}), accel(x={accel_data['x']:.2f}, y={accel_data['y']:.2f}, z={accel_data['z']:.2f})")
            time.sleep(PUBLISH_FREQUENCY)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
