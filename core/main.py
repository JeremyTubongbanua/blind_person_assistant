import json
import time
import threading
import paho.mqtt.client as mqtt
from menu_option_handler import MenuOptionHandler
from state_handler import StateHandler
from credentials import get_aws_credentials
from util import send_tts, vibrate_cane_motors

class ButtonState:
    def __init__(self, MQTT_HOST='192.168.2.219', MQTT_PORT=1883, MQTT_TOPIC='pi2/button_state'):
        self.MQTT_HOST = MQTT_HOST
        self.MQTT_PORT = MQTT_PORT
        self.MQTT_TOPIC = MQTT_TOPIC
        self.button_state = {'button1': False, 'button2': False, 'timestamp': 0}
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.right_press_callback = None
        self.left_press_callback = None
        self.debounce_time = 0.3  # 300ms debounce
        self.last_right_press_time = 0
        self.last_left_press_time = 0

        try:
            self.mqtt_client.connect(self.MQTT_HOST, self.MQTT_PORT, 60)
            mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
            mqtt_thread.start()
        except Exception as e:
            print(f"Error initializing MQTT client: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(self.MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            prev_button_state = self.button_state.copy()
            self.button_state = payload
            # print(f"Received button state: {self.button_state}")

            current_time = time.time()

            if self.button_state['button2'] and not prev_button_state['button2']:
                if current_time - self.last_right_press_time > self.debounce_time:
                    self.last_right_press_time = current_time
                    if self.right_press_callback:
                        threading.Thread(target=self.right_press_callback, daemon=True).start()

            if self.button_state['button1'] and not prev_button_state['button1']:
                if current_time - self.last_left_press_time > self.debounce_time:
                    self.last_left_press_time = current_time
                    if self.left_press_callback:
                        threading.Thread(target=self.left_press_callback, daemon=True).start()

        except json.JSONDecodeError:
            print(f"Error decoding JSON: {msg.payload}")
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def set_right_press_callback(self, callback):
        self.right_press_callback = callback

    def set_left_press_callback(self, callback):
        self.left_press_callback = callback

    def get_button_state(self):
        return self.button_state

class PYRState:
    def __init__(self, MQTT_HOST='192.168.2.219', MQTT_PORT=1883, MQTT_TOPIC='pi2/pitch_yaw_roll'):
        self.pyr_state = {'pitch': 0, 'yaw': 0, 'roll': 0}
        self.MQTT_HOST = MQTT_HOST
        self.MQTT_PORT = MQTT_PORT
        self.MQTT_TOPIC = MQTT_TOPIC
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        try:
            self.mqtt_client.connect(self.MQTT_HOST, self.MQTT_PORT, 60)
            mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
            mqtt_thread.start()
        except Exception as e:
            print(f"Error initializing MQTT client for Cane PYR state: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker for Cane PYR state with result code {rc}")
        client.subscribe(self.MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self.pyr_state = payload
            # print(f"Received Cane PYR state: {self.pyr_state}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON for Cane PYR state: {msg.payload}")
        except Exception as e:
            print(f"Error processing MQTT message for Cane PYR state: {e}")

    def get_pyr_state(self):
        return self.pyr_state

class ButtonState:
    def __init__(self, MQTT_HOST='192.168.2.219', MQTT_PORT=1883, MQTT_TOPIC='pi2/button_state'):
        self.MQTT_HOST = MQTT_HOST
        self.MQTT_PORT = MQTT_PORT
        self.MQTT_TOPIC = MQTT_TOPIC
        self.button_state = {'button1': False, 'button2': False, 'timestamp': 0}
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.right_press_callback = None
        self.left_press_callback = None
        self.debounce_time = 0.3  # 300ms debounce
        self.last_right_press_time = 0
        self.last_left_press_time = 0

        try:
            self.mqtt_client.connect(self.MQTT_HOST, self.MQTT_PORT, 60)
            mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
            mqtt_thread.start()
        except Exception as e:
            print(f"Error initializing MQTT client: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(self.MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            prev_button_state = self.button_state.copy()
            self.button_state = payload
            # print(f"Received button state: {self.button_state}")

            current_time = time.time()

            if self.button_state['button2'] and not prev_button_state['button2']:
                if current_time - self.last_right_press_time > self.debounce_time:
                    self.last_right_press_time = current_time
                    if self.right_press_callback:
                        threading.Thread(target=self.right_press_callback, daemon=True).start()

            if self.button_state['button1'] and not prev_button_state['button1']:
                if current_time - self.last_left_press_time > self.debounce_time:
                    self.last_left_press_time = current_time
                    if self.left_press_callback:
                        threading.Thread(target=self.left_press_callback, daemon=True).start()

        except json.JSONDecodeError:
            print(f"Error decoding JSON: {msg.payload}")
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def set_right_press_callback(self, callback):
        self.right_press_callback = callback

    def set_left_press_callback(self, callback):
        self.left_press_callback = callback

    def get_button_state(self):
        return self.button_state
            
class MenuSystem:
    def __init__(self, state_handler):
        self.state_handler = state_handler
                
        self.current_menu = "main"
        self.current_menu_index = 0
        
        self.menu_option_handler = MenuOptionHandler(self, state_handler)
        
        self.menus = {
            "main": [
                {"name": "Narrate Detections", "action": self.menu_option_handler.narrate_detections},
                {"name": "Track Object", "action": self.menu_option_handler.track_object},
                {"name": "Object Avoidance", "action": self.menu_option_handler.object_avoidance},
                {"name": "Scan Sign", "action": self.menu_option_handler.scan_sign},
                {"name": "Gyro Settings", "submenu": "gyro"},
                {"name": "Camera Settings", "submenu": "camera"},
                {"name": "Volume Settings", "submenu": "volume"},
                {"name": "Text To Speech Settings", "submenu": "tts"},
            ],
            "gyro": [
                {"name": "Calibrate Gyros", "action": self.menu_option_handler.calibrate_gyros},
                {"name": "Zero Pitch Yaw Roll", "action": self.menu_option_handler.zero_pitch_yaw_roll},
                {"name": "Narrate Gyro Values", "action": self.menu_option_handler.narrate_gyro_values},
                {"name": "Narrate Pitch Yaw Roll", "action": self.menu_option_handler.narrate_pitch_yaw_roll},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "camera": [
                {"name": "Start Camera", "action": self.menu_option_handler.start_camera},
                {"name": "Stop Camera", "action": self.menu_option_handler.stop_camera},
                {"name": "Restart Camera", "action": self.menu_option_handler.restart_camera},
                {"name": "Camera Status", "action": self.menu_option_handler.camera_status},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "volume": [
                {"name": "Get Volume", "action": self.menu_option_handler.get_volume},
                {"name": "Decrease Volume by 10", "action": self.menu_option_handler.decrease_volume},
                {"name": "Increase Volume by 10", "action": self.menu_option_handler.increase_volume},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "tts": [
                {"name": "Increase Text To Speech Speed by 25", "action": self.menu_option_handler.increase_tts_speed},
                {"name": "Decrease Text To Speech Speed by 25", "action": self.menu_option_handler.decrease_tts_speed},
                {"name": "Change Language to English", "action": self.menu_option_handler.set_language_to_english},
                {"name": "Change Language to French", "action": self.menu_option_handler.set_language_to_french},
                {"name": "Back to Main Menu", "submenu": "main"}
            ]
        }
        
        self.button_state = ButtonState()
        self.button_state.set_right_press_callback(self.handle_right_button)
        self.button_state.set_left_press_callback(self.handle_left_button)
        self.tts_speed = self.state_handler.get_state('tts_speed')
        self.voice_name = self.state_handler.get_state('voice_name')
        
        self.headset_pyr_state = PYRState(MQTT_HOST='localhost', MQTT_TOPIC='pi4/pitch_yaw_roll')
        self.cane_pyr_state = PYRState()
                
    def set_default_button_callbacks(self):
        print('Returned to Main Menu')
        self.button_state.set_right_press_callback(self.handle_right_button)
        self.button_state.set_left_press_callback(self.handle_left_button)
        
    def send_tts_configured(self, text):
        send_tts(text, self.tts_speed, self.voice_name)

    def handle_right_button(self):
        self.cycle_menu()
        self.announce_current_option()

    def handle_left_button(self):
        self.select_current_option()

    def cycle_menu(self):
        self.current_menu_index = (self.current_menu_index + 1) % len(self.menus[self.current_menu])
        print(f"Cycled to: {self.menus[self.current_menu][self.current_menu_index]['name']}")
        
    def announce_current_option(self):
        current_option = self.menus[self.current_menu][self.current_menu_index]
        option_name = current_option['name']
        self.send_tts_configured(option_name)
        
    def select_current_option(self):
        current_option = self.menus[self.current_menu][self.current_menu_index]
        
        if "submenu" in current_option:
            previous_menu = self.current_menu
            self.current_menu = current_option["submenu"]
            self.current_menu_index = 0
            
            vibrate_cane_motors(left_duration=0.1, right_duration=0.1)
            
            if previous_menu != self.current_menu:
                menu_name = f"{self.current_menu} menu"
                self.send_tts_configured(menu_name)
                time.sleep(1)
                self.announce_current_option()
        elif "action" in current_option:
            vibrate_cane_motors(left_duration=0.1, right_duration=0.1)
            current_option["action"]()

    def run(self):
        self.send_tts_configured(f"{self.current_menu} menu")
        time.sleep(1)
        self.announce_current_option()
        
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("Exiting menu system")

def main():
    get_aws_credentials()
    state_handler = StateHandler(state_file='state.json')
    state_handler.load_state()
    menu_system = MenuSystem(state_handler)
    menu_system.run()

if __name__ == "__main__":
    main()