import time
import json
import paho.mqtt.client as mqtt
from mpu6050 import mpu6050

MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/gyro"
MPU_ADDRESS = 0x68
PUBLISH_FREQUENCY = 0.05

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
        dict: Combined accelerometer and gyroscope data with the format matching requirements
    """
    accel_data = sensor.get_accel_data()
    gyro_data = sensor.get_gyro_data()
    
    # Format according to the specified JSON structure
    formatted_data = {
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
    
    return formatted_data

def publish_sensor_data(client, sensor_data):
    """
    Publish sensor data to the MQTT topic.
    
    Args:
        client: MQTT client instance
        sensor_data: Dictionary containing sensor readings
    """
    message = json.dumps(sensor_data)
    client.publish(MQTT_TOPIC, message)
    return sensor_data

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
            published_data = publish_sensor_data(mqtt_client, sensor_data)
            
            print(f"Published: {published_data}")
            
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