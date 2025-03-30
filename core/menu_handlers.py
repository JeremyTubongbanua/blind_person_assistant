import requests
import asyncio
import subprocess
import os
import paho.mqtt.client as mqtt
import json
from time import sleep

SPEAKER_API_URL = "http://localhost:5001"
TTS_URL = "http://localhost:5001/tts"

class MenuHandlers:
    def __init__(self, menu_system, state_handler):
        self.menu_system = menu_system
        self.state_handler = state_handler
        
    def send_tts(self, text, speed=None, voice_name=None):
        if speed is None:
            speed = self.tts_speed
        if voice_name is None:
            voice_name = self.tts_language
            
        try:
            if voice_name and voice_name.lower() == "fr-fr":
                try:
                    translator = Translator()
                    
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    translated = loop.run_until_complete(translator.translate(text, dest='fr'))
                    
                    text = translated.text
                    self.mqtt_handler.publish_log(f"Translated to French: {text}")
                except Exception as e:
                    self.mqtt_handler.publish_log(f"Translation error: {e}, using original text")
                    
            url = f"{TTS_URL}?text={text}&speed={speed}&voice_name={voice_name}"
            response = requests.get(url)
            if response.status_code != 200:
                self.mqtt_handler.publish_log(f"TTS request failed with status code {response.status_code}")
        except Exception as e:
            self.mqtt_handler.publish_log(f"Error sending TTS request: {e}")
    
    def narrate_detections(self):
        endpoint = 'http://localhost:8005/detections'
        response = requests.get(endpoint)
        sleep(0.1)
        
        if response.status_code == 200:
            data = response.json()
            num_detections = data.get('num_detections', 0)
            detections = data.get('detections', [])
            if num_detections > 0:
                message = f"Detected {num_detections} objects: "
                for detection in detections:
                    label = detection.get('label', 'unknown')
                    confidence = detection.get('confidence', 0)
                    message += f"{label} with confidence {confidence:.2f}, "
                message = message.rstrip(", ")
                self.menu_system.send_tts(message)
            else:
                self.menu_system.send_tts("No objects detected.")
        else: 
            self.menu_system.send_tts(f"Error fetching detections: {response.status_code}")
    
    def track_object(self):
        pass
    
    def scan_sign(self):
        pass

    def object_avoidance(self):
        pass
    
    def calibrate_gyros(self):
        try:
            self.menu_system.send_tts("Please do not move the headset or the cane. Calibration is starting.")
            # First API call (Headset)
            response = requests.post("http://localhost:5002/calibrate")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Gyroscope calibration on the headset completed successfully.")
                else:
                    self.menu_system.send_tts(f"Gyroscope calibration on the headset failed: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to calibrate gyroscope on the headset, response code: {response.status_code}")
            
            # Second API call (Smart Cane)
            response = requests.post("http://192.168.2.219:5002/calibrate")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Gyroscope calibration on the smart cane completed successfully.")
                else:
                    self.menu_system.send_tts(f"Gyroscope calibration on the smart cane failed: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to calibrate gyroscope on the smart cane, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error during gyroscope calibration: {str(e)}")
    
    def zero_pitch_yaw_roll(self):
        try:
            self.menu_system.send_tts("Zeroing pitch, yaw, and roll. Please hold the device steady.")
            
            # First API call (Headset)
            response = requests.post("http://localhost:5002/zero")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Pitch, yaw, and roll on the headset have been zeroed successfully.")
                else:
                    self.menu_system.send_tts(f"Failed to zero pitch, yaw, and roll on the headset: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to zero pitch, yaw, and roll on the headset, response code: {response.status_code}")
            
            sleep(3)
            
            # Second API call (Smart Cane)
            response = requests.post("http://192.168.2.219:5002/zero")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Pitch, yaw, and roll on the smart cane have been zeroed successfully.")
                else:
                    self.menu_system.send_tts(f"Failed to zero pitch, yaw, and roll on the smart cane: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to zero pitch, yaw, and roll on the smart cane, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error during zeroing pitch, yaw, and roll: {str(e)}")
    
    def narrate_gyro_values(self):
        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                gyro = payload.get("gyro", {})
                accel = payload.get("accel", {})

                gyro_x = gyro.get("x", 0)
                gyro_y = gyro.get("y", 0)
                gyro_z = gyro.get("z", 0)

                accel_x = accel.get("x", 0)
                accel_y = accel.get("y", 0)
                accel_z = accel.get("z", 0)

                message = (
                    f"Gyro values are X: {gyro_x:.2f}, Y: {gyro_y:.2f}, Z: {gyro_z:.2f}. "
                    f"Acceleration values are X: {accel_x:.2f}, Y: {accel_y:.2f}, Z: {accel_z:.2f}."
                )
                self.menu_system.send_tts(message)
            except Exception as e:
                self.menu_system.send_tts(f"Error processing gyro data: {str(e)}")
            client.loop_stop()
            client.disconnect()

        client = mqtt.Client()
        client.on_message = on_message

        try:
            client.connect("localhost", 1883, 60)
            client.subscribe("pi4/gyro")
            client.loop_start()
        except Exception as e:
            self.menu_system.send_tts(f"Error connecting to MQTT broker: {str(e)}")
    
    def narrate_pitch_yaw_roll(self):
        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                pitch = payload.get("pitch", 0)
                yaw = payload.get("yaw", 0)
                roll = payload.get("roll", 0)

                message = (
                    f"Pitch is {pitch:.2f} degrees, "
                    f"Yaw is {yaw:.2f} degrees, "
                    f"Roll is {roll:.2f} degrees."
                )
                self.menu_system.send_tts(message)
            except Exception as e:
                self.menu_system.send_tts(f"Error processing pitch, yaw, roll data: {str(e)}")
            client.loop_stop()
            client.disconnect()

        client = mqtt.Client()
        client.on_message = on_message

        try:
            client.connect("localhost", 1883, 60)
            client.subscribe("pi4/pitch_yaw_roll")
            client.loop_start()
        except Exception as e:
            self.menu_system.send_tts(f"Error connecting to MQTT broker: {str(e)}")
    
    def start_camera(self):
        try:
            response = requests.post("http://localhost:8010/start")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Camera started successfully")
                else:
                    self.menu_system.send_tts(f"Failed to start camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to start camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error starting camera: {str(e)}")
    
    def stop_camera(self):
        try:
            response = requests.post("http://localhost:8010/stop")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Camera stopped successfully")
                else:
                    self.menu_system.send_tts(f"Failed to stop camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to stop camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error stopping camera: {str(e)}")
    
    def restart_camera(self):
        try:
            response = requests.post("http://localhost:8010/restart")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts("Camera restarted successfully")
                else:
                    self.menu_system.send_tts(f"Failed to restart camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts(f"Failed to restart camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error restarting camera: {str(e)}")
    
    def camera_status(self):
        try:
            response = requests.get("http://localhost:8010/status")
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    if "status" in data:
                        status = data["status"]
                        if status == "disconnected":
                            self.menu_system.send_tts("Camera is disconnected")
                        elif status == "busy":
                            self.menu_system.send_tts("Camera is busy running detection")
                        elif status == "unavailable":
                            self.menu_system.send_tts("Camera is unavailable or in use by another application")
                        elif status == "error":
                            self.menu_system.send_tts(f"Camera error: {data['error']}")
                        else:
                            self.menu_system.send_tts(f"Camera status: {status}")
                    else:
                        self.menu_system.send_tts(f"Camera error: {data['error']}")
                else:
                    self.menu_system.send_tts("Camera is working properly")
            else:
                self.menu_system.send_tts(f"Failed to get camera status, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts(f"Error checking camera status: {str(e)}")
    
    def get_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                volume_data = response.json()
                volume = volume_data.get("volume", 0)
                self.menu_system.send_tts(f"Current volume is {volume} percent")
                return volume
            else:
                self.menu_system.send_tts("Failed to get volume information")
                return None
        except Exception as e:
            self.menu_system.send_tts(f"Error getting volume: {str(e)}")
            return None
    
    def decrease_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                current_volume = response.json().get("volume", 0)
                new_volume = max(10, current_volume - 10)
                
                set_response = requests.get(f"{SPEAKER_API_URL}/set_volume", params={"volume": new_volume})
                if set_response.status_code == 200:
                    self.menu_system.send_tts(f"Volume decreased to {new_volume} percent")
                    return new_volume
                else:
                    self.menu_system.send_tts("Failed to decrease volume")
                    return None
            else:
                self.menu_system.send_tts("Failed to get current volume")
                return None
        except Exception as e:
            self.menu_system.send_tts(f"Error decreasing volume: {str(e)}")
            return None
    
    def increase_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                current_volume = response.json().get("volume", 0)
                new_volume = min(100, current_volume + 10)
                
                set_response = requests.get(f"{SPEAKER_API_URL}/set_volume", params={"volume": new_volume})
                if set_response.status_code == 200:
                    self.menu_system.send_tts(f"Volume increased to {new_volume} percent")
                    return new_volume
                else:
                    self.menu_system.send_tts("Failed to increase volume")
                    return None
            else:
                self.menu_system.send_tts("Failed to get current volume")
                return None
        except Exception as e:
            self.menu_system.send_tts(f"Error increasing volume: {str(e)}")
            return None
    
    def increase_tts_speed(self):
        try:
            current_speed = self.state_handler.get_state("tts_speed", 150)
            new_speed = min(300, current_speed + 25)
            
            self.state_handler.set_state("tts_speed", new_speed)
            self.state_handler.save_state()
            
            self.menu_system.tts_speed = new_speed
            self.menu_system.send_tts(f"Text to speech speed increased to {new_speed}", speed=new_speed)
            return new_speed
        except Exception as e:
            self.menu_system.send_tts(f"Error changing speed: {str(e)}")
            return None

    def decrease_tts_speed(self):
        try:
            current_speed = self.state_handler.get_state("tts_speed", 150)
            new_speed = max(100, current_speed - 25)
            
            self.state_handler.set_state("tts_speed", new_speed)
            self.state_handler.save_state()
            
            self.menu_system.tts_speed = new_speed
            self.menu_system.send_tts(f"Text to speech speed decreased to {new_speed}", speed=new_speed)
            return new_speed
        except Exception as e:
            self.menu_system.send_tts(f"Error changing speed: {str(e)}")
            return None
    
    def set_language_to_english(self):
        try:
            language = "en-US"
            
            self.state_handler.set_state("tts_language", language)
            self.state_handler.save_state()
            
            self.menu_system.tts_language = language
            self.menu_system.send_tts("Text to speech language set to English", voice_name=language)
            return language
        except Exception as e:
            self.menu_system.send_tts(f"Error setting language: {str(e)}")
            return None
    
    def set_language_to_french(self):
        try:
            language = "fr-FR"
            
            self.state_handler.set_state("tts_language", language)
            self.state_handler.save_state()
            
            self.menu_system.tts_language = language
            self.menu_system.send_tts("Text to speech language set to French", voice_name=language)
            return language
        except Exception as e:
            self.menu_system.send_tts(f"Error setting language: {str(e)}")
            return None
