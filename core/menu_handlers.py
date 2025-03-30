import requests
import asyncio

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
    
    def announce_detections(self):
        pass
    
    def scan_sign(self):
        pass
    
    def track_object(self):
        pass
    
    def object_avoidance(self):
        pass
    
    def calibrate_gyros(self):
        pass
    
    def narrate_gyro_values(self):
        pass
    
    def narrate_pitch_yaw_roll(self):
        pass
    
    def start_camera(self):
        pass
    
    def stop_camera(self):
        pass
    
    def restart_camera(self):
        pass
    
    def camera_status(self):
        pass
    
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
            new_speed = min(250, current_speed + 25)
            
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