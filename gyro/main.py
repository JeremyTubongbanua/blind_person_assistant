import time
import json
import paho.mqtt.client as mqtt
from mpu6050 import mpu6050

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/gyro"
MPU_ADDRESS = 0x68
PUBLISH_FREQUENCY = 0.5  # 2Hz

def setup_mqtt():
    """
    Initialize and connect to the MQTT broker.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    return client

def setup_sensor():
    """
    Initialize and configure the MPU-6050 sensor.
    """
    sensor = mpu6050(MPU_ADDRESS)
    sensor.set_gyro_range(sensor.GYRO_RANGE_500DEG)
    sensor.set_accel_range(sensor.ACCEL_RANGE_2G)
    sensor.set_filter_range(sensor.FILTER_BW_20)
    return sensor

def read_sensor_data(sensor):
    """
    Read acceleration and gyroscope data from the sensor.
    
    Returns:
        dict: Combined accelerometer and gyroscope data
    """
    accel_data = sensor.get_accel_data()
    gyro_data = sensor.get_gyro_data()
    
    return {
        "accel": accel_data,
        "gyro": gyro_data
    }

def publish_sensor_data(client, sensor_data):
    """
    Publish sensor data to the MQTT topic.
    
    Args:
        client: MQTT client instance
        sensor_data: Dictionary containing sensor readings
    """
    payload = {
        "accel_x": sensor_data["accel"]["x"],
        "accel_y": sensor_data["accel"]["y"],
        "accel_z": sensor_data["accel"]["z"],
        "gyro_x": sensor_data["gyro"]["x"],
        "gyro_y": sensor_data["gyro"]["y"],
        "gyro_z": sensor_data["gyro"]["z"],
        "timestamp": time.time()
    }
    
    message = json.dumps(payload)
    client.publish(MQTT_TOPIC, message)
    return payload

def main():
    """
    Main function to run the gyroscope data monitoring and MQTT publishing.
    """
    try:
        mqtt_client = setup_mqtt()
        sensor = setup_sensor()
        
        print(f"Starting MPU-6050 data publisher on topic: {MQTT_TOPIC}")
        print(f"Publishing frequency: {PUBLISH_FREQUENCY} seconds")
        
        while True:
            sensor_data = read_sensor_data(sensor)
            payload = publish_sensor_data(mqtt_client, sensor_data)
            
            print(f"Published: {payload}")
            
            time.sleep(PUBLISH_FREQUENCY)
            
    except KeyboardInterrupt:
        print("Exiting program")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'mqtt_client' in locals():
            mqtt_client.loop_stop()

if __name__ == "__main__":
    main()