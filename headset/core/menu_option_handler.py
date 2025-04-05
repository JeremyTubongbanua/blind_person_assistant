import asyncio
import os
import paho.mqtt.client as mqtt
import json
from time import sleep
import time
import requests
import boto3
import io
from PIL import Image
import base64
from util import camera_detections, zero_pyr_cane, zero_pyr_headset, vibrate_cane_motors

SPEAKER_API_URL = "http://localhost:5001"

class MenuOptionHandler:
    def __init__(self, menu_system, state_handler):
        self.menu_system = menu_system
        self.state_handler = state_handler
    
    def narrate_detections(self):
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        num_detections = data.get('num_detections', 0)
        detections = data.get('detections', [])
        if num_detections > 0 and detections:
            message = f"Detected {num_detections} objects: "
            for detection in detections:
                label = detection.get('label', 'unknown')
                distance = detection.get('distance', 0)
                confidence = detection.get('confidence', 0)
                message += f"{label} with confidence {confidence:.2f}, {distance:.1f} meters away, "
            message = message.rstrip(", ")
            self.menu_system.send_tts_configured(message)
        else:
            self.menu_system.send_tts_configured("No objects detected. Please walk to a sign.")

    def track_object(self):
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        detections = data.get('detections', [])
        
        if not detections:
            self.menu_system.send_tts_configured("No objects detected. Point camera at objects to track.")
            return
        
        num_detections = len(detections)
        self.menu_system.send_tts_configured(f"{num_detections} objects detected. Use button 2 to cycle through objects and button 1 to select.")
        print(f'Detections: {detections}')
        sleep(4)
        current_index = 0
        selected_object = None

        def narrate_current_object():
            detection = detections[current_index]
            label = detection.get('label', 'unknown')
            distance = detection.get('distance', 0)
            confidence = detection.get('confidence', 0)
            self.menu_system.send_tts_configured(
                f"Object {current_index + 1}: {label}, {distance:.1f} meters away, confidence {confidence:.2f}."
            )

        narrate_current_object()
        
        def right_button_callback():
            nonlocal current_index
            current_index = (current_index + 1) % len(detections)
            narrate_current_object()

        def left_button_callback():
            nonlocal selected_object
            selected_object = detections[current_index]
            label = selected_object.get('label', 'unknown')
            self.menu_system.send_tts_configured(f"Starting tracking loop for {label}.")
            
            zero_pyr_cane()
            zero_pyr_headset()
            
            print(selected_object)
            
            bbox = selected_object.get('bbox', {})
            if bbox:
                x1, x2 = bbox.get('x1', 0), bbox.get('x2', 0)
                y1, y2 = bbox.get('y1', 0), bbox.get('y2', 0)
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                camera_width = 320
                camera_height = 320

                camera_center_x = camera_width / 2
                camera_center_y = camera_height / 2
                print(f"Camera center coordinate: ({camera_center_x}, {camera_center_y})")
                
                distance = selected_object.get('distance', 0)
                
                pixel_offset_x = center_x - camera_center_x
                
                import math
                ndc_x = pixel_offset_x / camera_center_x
                
                horizontal_fov_half = math.radians(31)
                horizontal_angle = math.degrees(math.atan(math.tan(horizontal_fov_half) * ndc_x))
                
                pixel_offset_y = center_y - camera_center_y
                ndc_y = pixel_offset_y / camera_center_y
                vertical_fov_half = math.radians(24)
                vertical_angle = -math.degrees(math.atan(math.tan(vertical_fov_half) * ndc_y))

                print(f"Horizontal angle: {horizontal_angle:.2f} degrees")
                print(f"Vertical angle: {vertical_angle:.2f} degrees")
                
                lateral_displacement = distance * math.tan(math.radians(horizontal_angle))
                print(f"Lateral displacement: {lateral_displacement:.2f} meters")
                
                direction = "right" if horizontal_angle > 0 else "left"
                magnitude = abs(horizontal_angle)
                
                if magnitude < 5:
                    direction_desc = "slightly to your " + direction
                elif magnitude < 15:
                    direction_desc = "to your " + direction
                elif magnitude < 30:
                    direction_desc = "far to your " + direction
                else:
                    direction_desc = "very far to your " + direction
                
                sleep(2.5)
                self.menu_system.send_tts_configured(
                    f"Object is {distance:.1f} meters away, {magnitude:.1f} degrees {direction_desc}."
                )
                                
                def cancel_tracking_callback():
                    nonlocal tracking
                    tracking = False
                    self.menu_system.send_tts_configured("Object tracking canceled.")
                    self.menu_system.set_default_button_callbacks()

                self.menu_system.button_state.set_left_press_callback(cancel_tracking_callback)
                
                tracking = True
                while tracking:
                    headset_pyr = self.menu_system.headset_pyr_state.get_pyr_state()
                    cane_pyr = self.menu_system.cane_pyr_state.get_pyr_state()
                    headset_yaw = headset_pyr.get('yaw')
                    cane_yaw = cane_pyr.get('yaw')
                    print(f'{cane_yaw} and {horizontal_angle}')
                    if abs(cane_yaw - horizontal_angle) <= 10:
                        vibrate_cane_motors(left_duration=0.5, right_duration=0.5)
                    sleep(0.5)  # Add a delay to avoid excessive vibrations

        try:
            self.menu_system.button_state.set_right_press_callback(right_button_callback)
            self.menu_system.button_state.set_left_press_callback(left_button_callback)

            while selected_object is None:
                sleep(0.1)  # Wait for button press callbacks to handle the logic
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error during object tracking: {str(e)}")
        finally:
            self.menu_system.set_default_button_callbacks()        

    def object_avoidance(self):
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        detections = data.get('detections', [])
        
        if not detections:
            self.menu_system.send_tts_configured("No objects detected. Point camera at surroundings to detect objects.")
            return
        
        num_detections = len(detections)
        self.menu_system.send_tts_configured(f"{num_detections} objects detected. Starting object avoidance mode.")
        
        zero_pyr_cane()
        zero_pyr_headset()
        
        import math
        camera_width = 320
        camera_height = 320
        camera_center_x = camera_width / 2
        camera_center_y = camera_height / 2
        
        def get_object_positions():
            response = camera_detections()
            if response.status_code != 200:
                return []
            
            data = response.json()
            detections = data.get('detections', [])
            
            object_positions = []
            for detection in detections:
                bbox = detection.get('bbox', {})
                if bbox:
                    x1, x2 = bbox.get('x1', 0), bbox.get('x2', 0)
                    y1, y2 = bbox.get('y1', 0), bbox.get('y2', 0)
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    pixel_offset_x = center_x - camera_center_x
                    ndc_x = pixel_offset_x / camera_center_x
                    
                    horizontal_fov_half = math.radians(31)
                    horizontal_angle = math.degrees(math.atan(math.tan(horizontal_fov_half) * ndc_x))
                    
                    distance = detection.get('distance', 0)
                    
                    object_positions.append({
                        'angle': horizontal_angle,
                        'distance': distance,
                        'label': detection.get('label', 'unknown')
                    })
            
            return object_positions
        
        def cancel_avoidance_callback():
            nonlocal avoidance_active
            avoidance_active = False
            self.menu_system.send_tts_configured("Object avoidance canceled.")
            self.menu_system.set_default_button_callbacks()
        
        self.menu_system.button_state.set_left_press_callback(cancel_avoidance_callback)
        
        avoidance_active = True
        last_report_time = 0
        
        while avoidance_active:
            try:
                objects = get_object_positions()
                headset_pyr = self.menu_system.headset_pyr_state.get_pyr_state()
                cane_pyr = self.menu_system.cane_pyr_state.get_pyr_state()
                cane_yaw = cane_pyr.get('yaw', 0)
                
                for obj in objects:
                    angle = obj['angle']
                    distance = obj['distance']
                    
                    relative_angle = angle - cane_yaw
                    
                    if distance < 2.0 and abs(relative_angle) <= 10:
                        if relative_angle < -5:
                            vibrate_cane_motors(left_duration=0.3, right_duration=0)
                        elif relative_angle > 5:
                            vibrate_cane_motors(left_duration=0, right_duration=0.3)
                        else:
                            vibrate_cane_motors(left_duration=0.3, right_duration=0.3)
                    
                    current_time = time.time()
                    if current_time - last_report_time > 5:
                        closest_obj = min(objects, key=lambda x: x['distance']) if objects else None
                        if closest_obj:
                            direction = "right" if closest_obj['angle'] > 0 else "left"
                            self.menu_system.send_tts_configured(
                                f"Closest object is {closest_obj['label']}, {closest_obj['distance']:.1f} meters away to your {direction}."
                            )
                            last_report_time = current_time
                        
                sleep(0.2)
            except Exception as e:
                self.menu_system.send_tts_configured(f"Error in object avoidance: {str(e)}")
                break
        
        self.menu_system.set_default_button_callbacks()
    
    def scan_sign(self):        
        try:
            response = camera_detections()
            if response.status_code != 200:
                self.menu_system.send_tts_configured("Error fetching detections. Camera may be off.")
                return
            
            data = response.json()
            detections = data.get('detections', [])
            
            sign_detections = [d for d in detections if d.get('label') == 'general_sign']
            
            if not sign_detections:
                self.menu_system.send_tts_configured("No signs detected. Please point the camera at a sign.")
                return
            
            self.menu_system.send_tts_configured("Sign detected. Processing...")
            
            sign = sign_detections[0]
            bbox = sign.get('bbox', {})
            
            img_data = base64.b64decode(data.get('detection_image', ''))
            if not img_data:
                self.menu_system.send_tts_configured("Failed to get detection image.")
                return
            
            img = Image.open(io.BytesIO(img_data))
            
            img_width, img_height = img.size
            x1 = max(0, int(bbox.get('x1', 0)))
            y1 = max(0, int(bbox.get('y1', 0)))
            x2 = min(img_width, int(bbox.get('x2', 0)))
            y2 = min(img_height, int(bbox.get('y2', 0)))
            
            if x2 <= x1 or y2 <= y1:
                self.menu_system.send_tts_configured("Invalid sign boundaries.")
                return
            
            cropped_img = img.crop((x1, y1, x2, y2))
            
            try:
                textract = boto3.client('textract', region_name='us-east-2')
                img_byte_arr = io.BytesIO()
                cropped_img.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                
                textract_response = textract.detect_document_text(
                    Document={'Bytes': img_byte_arr}
                )
                
                extracted_text = ""
                for item in textract_response['Blocks']:
                    if item['BlockType'] == 'LINE':
                        extracted_text += item['Text'] + " "
                
                if extracted_text.strip():
                    self.menu_system.send_tts_configured(f"Sign says: {extracted_text}")
                    return
            except Exception:
                pass
            
            try:
                import pytesseract
                extracted_text = pytesseract.image_to_string(cropped_img)
                
                if extracted_text.strip():
                    self.menu_system.send_tts_configured(f"Sign says: {extracted_text}")
                    return
                else:
                    self.menu_system.send_tts_configured("No text found on the sign.")
                    return
            except Exception as e:
                self.menu_system.send_tts_configured(f"Error reading sign text: {str(e)}")
                
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error scanning sign: {str(e)}")
    
    def calibrate_gyros(self):
        try:
            self.menu_system.send_tts_configured("Please do not move the headset or the cane. Calibration is starting.")
            # First API call (Headset)
            response = requests.post("http://localhost:5002/calibrate")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Gyroscope calibration on the headset completed successfully.")
                else:
                    self.menu_system.send_tts_configured(f"Gyroscope calibration on the headset failed: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to calibrate gyroscope on the headset, response code: {response.status_code}")
            
            # Second API call (Smart Cane)
            response = requests.post("http://192.168.2.219:5002/calibrate")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Gyroscope calibration on the smart cane completed successfully.")
                else:
                    self.menu_system.send_tts_configured(f"Gyroscope calibration on the smart cane failed: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to calibrate gyroscope on the smart cane, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error during gyroscope calibration: {str(e)}")
    
    def zero_pitch_yaw_roll(self):
        try:
            self.menu_system.send_tts_configured("Zeroing pitch, yaw, and roll. Please hold the device steady.")
            
            # First API call (Headset)
            response = zero_pyr_headset()
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Pitch, yaw, and roll on the headset have been zeroed successfully.")
                else:
                    self.menu_system.send_tts_configured(f"Failed to zero pitch, yaw, and roll on the headset: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to zero pitch, yaw, and roll on the headset, response code: {response.status_code}")
            
            sleep(3)
            
            # Second API call (Smart Cane)
            response = zero_pyr_cane()
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Pitch, yaw, and roll on the smart cane have been zeroed successfully.")
                else:
                    self.menu_system.send_tts_configured(f"Failed to zero pitch, yaw, and roll on the smart cane: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to zero pitch, yaw, and roll on the smart cane, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error during zeroing pitch, yaw, and roll: {str(e)}")
    
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
                self.menu_system.send_tts_configured(message)
            except Exception as e:
                self.menu_system.send_tts_configured(f"Error processing gyro data: {str(e)}")
            client.loop_stop()
            client.disconnect()

        client = mqtt.Client()
        client.on_message = on_message

        try:
            client.connect("localhost", 1883, 60)
            client.subscribe("pi4/gyro")
            client.loop_start()
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error connecting to MQTT broker: {str(e)}")
    
    def narrate_pitch_yaw_roll(self):
        pyr_state = self.menu_system.headset_pyr_state.get_pyr_state()
        pitch = pyr_state.get('pitch')
        yaw = pyr_state.get('yaw')
        roll = pyr_state.get('roll')
        self.menu_system.send_tts_configured(
            f"Pitch is {pitch:.2f} degrees, yaw is {yaw:.2f} degrees, and roll is {roll:.2f} degrees."
        )
    
    def start_camera(self):
        try:
            response = requests.post("http://localhost:8010/start")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Camera started successfully")
                else:
                    self.menu_system.send_tts_configured(f"Failed to start camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to start camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error starting camera: {str(e)}")
    
    def stop_camera(self):
        try:
            response = requests.post("http://localhost:8010/stop")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Camera stopped successfully")
                else:
                    self.menu_system.send_tts_configured(f"Failed to stop camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to stop camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error stopping camera: {str(e)}")
    
    def restart_camera(self):
        try:
            response = requests.post("http://localhost:8010/restart")
            if response.status_code == 200:
                data = response.json()
                if data.get("status", False):
                    self.menu_system.send_tts_configured("Camera restarted successfully")
                else:
                    self.menu_system.send_tts_configured(f"Failed to restart camera: {data.get('error', 'Unknown error')}")
            else:
                self.menu_system.send_tts_configured(f"Failed to restart camera, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error restarting camera: {str(e)}")
    
    def camera_status(self):
        try:
            response = requests.get("http://localhost:8010/status")
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    if "status" in data:
                        status = data["status"]
                        if status == "disconnected":
                            self.menu_system.send_tts_configured("Camera is disconnected")
                        elif status == "busy":
                            self.menu_system.send_tts_configured("Camera is busy running detection")
                        elif status == "unavailable":
                            self.menu_system.send_tts_configured("Camera is unavailable or in use by another application")
                        elif status == "error":
                            self.menu_system.send_tts_configured(f"Camera error: {data['error']}")
                        else:
                            self.menu_system.send_tts_configured(f"Camera status: {status}")
                    else:
                        self.menu_system.send_tts_configured(f"Camera error: {data['error']}")
                else:
                    self.menu_system.send_tts_configured("Camera is working properly")
            else:
                self.menu_system.send_tts_configured(f"Failed to get camera status, response code: {response.status_code}")
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error checking camera status: {str(e)}")
    
    def get_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                volume_data = response.json()
                volume = volume_data.get("volume", 0)
                self.menu_system.send_tts_configured(f"Current volume is {volume} percent")
                return volume
            else:
                self.menu_system.send_tts_configured("Failed to get volume information")
                return None
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error getting volume: {str(e)}")
            return None
    
    def decrease_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                current_volume = response.json().get("volume", 0)
                new_volume = max(10, current_volume - 10)
                
                set_response = requests.get(f"{SPEAKER_API_URL}/set_volume", params={"volume": new_volume})
                if set_response.status_code == 200:
                    self.menu_system.send_tts_configured(f"Volume decreased to {new_volume} percent")
                    return new_volume
                else:
                    self.menu_system.send_tts_configured("Failed to decrease volume")
                    return None
            else:
                self.menu_system.send_tts_configured("Failed to get current volume")
                return None
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error decreasing volume: {str(e)}")
            return None
    
    def increase_volume(self):
        try:
            response = requests.get(f"{SPEAKER_API_URL}/get_volume")
            if response.status_code == 200:
                current_volume = response.json().get("volume", 0)
                new_volume = min(100, current_volume + 10)
                
                set_response = requests.get(f"{SPEAKER_API_URL}/set_volume", params={"volume": new_volume})
                if set_response.status_code == 200:
                    self.menu_system.send_tts_configured(f"Volume increased to {new_volume} percent")
                    return new_volume
                else:
                    self.menu_system.send_tts_configured("Failed to increase volume")
                    return None
            else:
                self.menu_system.send_tts_configured("Failed to get current volume")
                return None
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error increasing volume: {str(e)}")
            return None
    
    def increase_tts_speed(self):
        try:
            current_speed = self.state_handler.get_state("tts_speed", 150)
            new_speed = min(300, current_speed + 25)
            
            self.state_handler.set_state("tts_speed", new_speed)
            self.state_handler.save_state()
            
            self.menu_system.tts_speed = new_speed
            self.menu_system.send_tts_configured(f"Text to speech speed increased to {new_speed}", speed=new_speed)
            return new_speed
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error changing speed: {str(e)}")
            return None

    def decrease_tts_speed(self):
        try:
            current_speed = self.state_handler.get_state("tts_speed", 150)
            new_speed = max(100, current_speed - 25)
            
            self.state_handler.set_state("tts_speed", new_speed)
            self.state_handler.save_state()
            
            self.menu_system.tts_speed = new_speed
            self.menu_system.send_tts_configured(f"Text to speech speed decreased to {new_speed}", speed=new_speed)
            return new_speed
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error changing speed: {str(e)}")
            return None
    
    def set_language_to_english(self):
        try:
            language = "en-US"
            
            self.state_handler.set_state("tts_language", language)
            self.state_handler.save_state()
            
            self.menu_system.tts_language = language
            self.menu_system.send_tts_configured("Text to speech language set to English", voice_name=language)
            return language
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error setting language: {str(e)}")
            return None
    
    def set_language_to_french(self):
        try:
            language = "fr-FR"
            
            self.state_handler.set_state("tts_language", language)
            self.state_handler.save_state()
            
            self.menu_system.tts_language = language
            self.menu_system.send_tts_configured("Text to speech language set to French", voice_name=language)
            return language
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error setting language: {str(e)}")
            return None
