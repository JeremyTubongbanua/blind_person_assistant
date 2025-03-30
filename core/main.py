import requests
import json
import time
import threading
import queue
import paho.mqtt.client as mqtt
from mqtt_handler import MqttHandler
from menu_handlers import MenuHandlers
from state_handler import StateHandler
from googletrans import Translator

TTS_URL = "http://localhost:5001/tts"
MQTT_BROKER = "192.168.2.219"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/button_state"

class MenuSystem:
    def __init__(self, state_handler):
        self.state_handler = state_handler
        self.button_state = {"button1": False, "button2": False, "timestamp": 0}
        self.button_event_queue = queue.Queue()
        self.button_subscribers = []
        self.running = True
        self.in_menu = True
        self.current_menu = "main"
        self.current_menu_index = 0
        self.tts_speed = self.state_handler.get_state("tts_speed", 150)
        self.tts_voice = self.state_handler.get_state("tts_voice", "en-US-Neural2-F")
        self.tts_language = self.state_handler.get_state("tts_language", "en-US")
        self.mqtt_client = None
        self.mqtt_handler = MqttHandler(MQTT_BROKER, MQTT_PORT, MQTT_TOPIC)
        
        self.menu_handlers = MenuHandlers(self, state_handler)
        
        self.menus = {
            "main": [
                {"name": "Announce Detections", "action": self.menu_handlers.announce_detections},
                {"name": "Scan Sign", "action": self.menu_handlers.scan_sign},
                {"name": "Track Object", "action": self.menu_handlers.track_object},
                {"name": "Object Avoidance", "action": self.menu_handlers.object_avoidance},
                {"name": "Gyro Settings", "submenu": "gyro"},
                {"name": "Camera Settings", "submenu": "camera"},
                {"name": "Volume Settings", "submenu": "volume"},
                {"name": "Text To Speech Settings", "submenu": "tts"},
            ],
            "gyro": [
                {"name": "Calibrate Gyros", "action": self.menu_handlers.calibrate_gyros},
                {"name": "Narrate Gyro Values", "action": self.menu_handlers.narrate_gyro_values},
                {"name": "Narrate Pitch Yaw Roll", "action": self.menu_handlers.narrate_pitch_yaw_roll},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "camera": [
                {"name": "Start Camera", "action": self.menu_handlers.start_camera},
                {"name": "Stop Camera", "action": self.menu_handlers.stop_camera},
                {"name": "Restart Camera", "action": self.menu_handlers.restart_camera},
                {"name": "Camera Status", "action": self.menu_handlers.camera_status},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "volume": [
                {"name": "Get Volume", "action": self.menu_handlers.get_volume},
                {"name": "Decrease Volume by 10", "action": self.menu_handlers.decrease_volume},
                {"name": "Increase Volume by 10", "action": self.menu_handlers.increase_volume},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "tts": [
                {"name": "Increase Text To Speech Speed by 25", "action": self.menu_handlers.increase_tts_speed},
                {"name": "Decrease Text To Speech Speed by 25", "action": self.menu_handlers.decrease_tts_speed},
                {"name": "Change Language to English", "action": self.menu_handlers.set_language_to_english},
                {"name": "Change Language to French", "action": self.menu_handlers.set_language_to_french},
                {"name": "Back to Main Menu", "submenu": "main"}
            ]
        }
        
        self.menu_history = []

    def publish_menu_structure(self):
        current_items = self.get_current_menu_items()
        menu_structure = self.mqtt_handler.format_menu_structure(
            self.current_menu,
            self.current_menu_index,
            current_items,
            self.menu_history
        )
        self.mqtt_handler.publish_menu(menu_structure)

    def send_tts(self, text, speed=None, voice_name=None):
        if speed is None:
            speed = self.tts_speed
        if voice_name is None:
            voice_name = self.tts_language
            
        try:
            if voice_name and voice_name.lower() == "fr-fr":
                try:
                    translator = Translator()
                    
                    import asyncio
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
            
    def button_event_worker(self):
        while self.running:
            try:
                event_data = self.button_event_queue.get(timeout=0.5)
                if event_data:
                    button, event = event_data
                    self.mqtt_handler.publish_log(f"Processing event: {button} {event}")
                    for subscriber in self.button_subscribers:
                        if subscriber:
                            try:
                                subscriber(button, event)
                            except Exception as e:
                                self.mqtt_handler.publish_log(f"Error in button subscriber: {e}")
                self.button_event_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                self.mqtt_handler.publish_log(f"Error in button event worker: {e}")

    def subscribe_to_buttons(self, callback):
        self.button_subscribers.append(callback)
        return len(self.button_subscribers) - 1

    def unsubscribe_from_buttons(self, subscriber_id):
        if 0 <= subscriber_id < len(self.button_subscribers):
            self.button_subscribers[subscriber_id] = None

    def on_connect(self, client, userdata, flags, rc):
        self.mqtt_handler.publish_log(f"Connected with result code {rc}")
        client.subscribe(MQTT_TOPIC)
        self.send_tts("Menu system connected. Use button 2 to cycle through options, button 1 to select.")
        self.publish_menu_structure()

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            prev_button1 = self.button_state["button1"]
            prev_button2 = self.button_state["button2"]
            
            self.button_state = payload
            
            self.mqtt_handler.publish_log(f"MQTT: B1: {prev_button1}->{self.button_state['button1']}, B2: {prev_button2}->{self.button_state['button2']}")
            
            if self.button_state["button1"] and not prev_button1:
                self.mqtt_handler.publish_log("Queuing button1 pressed event")
                self.button_event_queue.put(("button1", "pressed"))
                if self.in_menu:
                    self.select_current_option()
            elif not self.button_state["button1"] and prev_button1:
                self.mqtt_handler.publish_log("Queuing button1 released event")
                self.button_event_queue.put(("button1", "released"))
                
            if self.button_state["button2"] and not prev_button2:
                self.mqtt_handler.publish_log("Queuing button2 pressed event")
                self.button_event_queue.put(("button2", "pressed"))
                if self.in_menu:
                    self.cycle_menu()
            elif not self.button_state["button2"] and prev_button2:
                self.mqtt_handler.publish_log("Queuing button2 released event")
                self.button_event_queue.put(("button2", "released"))
            
        except json.JSONDecodeError:
            self.mqtt_handler.publish_log(f"Error decoding JSON: {msg.payload}")
        except Exception as e:
            self.mqtt_handler.publish_log(f"Error processing message: {e}")

    def get_current_menu_items(self):
        return self.menus.get(self.current_menu, [])

    def get_current_menu_option(self):
        items = self.get_current_menu_items()
        if not items:
            return "No options available"
        
        if 0 <= self.current_menu_index < len(items):
            return items[self.current_menu_index]["name"]
        else:
            self.current_menu_index = 0
            return items[0]["name"] if items else "No options available"

    def cycle_menu(self):
        items = self.get_current_menu_items()
        if not items:
            return
        
        self.current_menu_index = (self.current_menu_index + 1) % len(items)
        current_option = self.get_current_menu_option()
        option_index = self.current_menu_index + 1
        self.send_tts(f"option {option_index}: {current_option}")
        self.mqtt_handler.publish_log(f"Current menu option: {option_index}: {current_option}")
        self.publish_menu_structure()

    def select_current_option(self):
        items = self.get_current_menu_items()
        if not items or self.current_menu_index >= len(items):
            self.send_tts("No option available")
            return
        
        current_item = items[self.current_menu_index]
        current_option = current_item["name"]
        option_index = self.current_menu_index + 1
        self.send_tts(f"Selected {current_option}")
        self.mqtt_handler.publish_log(f"Selected option {option_index}: {current_option}")
        
        if "submenu" in current_item:
            submenu = current_item["submenu"]
            self.menu_history.append((self.current_menu, self.current_menu_index))
            self.current_menu = submenu
            self.current_menu_index = 0
            new_option = self.get_current_menu_option()
            new_index = self.current_menu_index + 1
            self.send_tts(f"Submenu {submenu}. option {new_index}: {new_option}")
            self.mqtt_handler.publish_log(f"Entered submenu {submenu}. Current option {new_index}: {new_option}")
            self.publish_menu_structure()
        elif "action" in current_item:
            action = current_item["action"]
            if action:
                try:
                    self.in_menu = False
                    action()
                    self.in_menu = True
                except Exception as e:
                    self.mqtt_handler.publish_log(f"Error executing action: {e}")
                    self.send_tts(f"Error executing action")
                    self.in_menu = True

    def init_mqtt(self):
        client = self.mqtt_handler.connect(
            lambda client, userdata, flags, rc: self.on_connect(client, userdata, flags, rc),
            lambda client, userdata, msg: self.on_message(client, userdata, msg)
        )
        
        if client is None:
            self.mqtt_handler.publish_log("Failed to initialize MQTT client")
            return None
            
        self.mqtt_client = client
        return client

    def run(self):
        client = self.init_mqtt()
        if client is None:
            print("Failed to initialize MQTT client. Exiting.")
            return
        
        self.mqtt_handler.publish_log("Starting button event worker thread")
        event_thread = threading.Thread(target=self.button_event_worker, daemon=True)
        event_thread.start()
        
        client.loop_start()
        
        current_option = self.get_current_menu_option()
        option_index = self.current_menu_index + 1
        self.send_tts(f"Menu system initialized.")
        self.send_tts(f"Current menu option {option_index}: {current_option}")
        self.publish_menu_structure()
        
        try:
            self.mqtt_handler.publish_log("Entering main loop")
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.mqtt_handler.publish_log("Interrupted by user")
        finally:
            self.running = False
            event_thread.join(timeout=1.0)
            client.loop_stop()
            client.disconnect()
            print("Exiting menu system")

def main():
    state_handler = StateHandler(state_file='state.json')
    state_handler.load_state()
    menu_system = MenuSystem(state_handler)
    menu_system.run()

if __name__ == "__main__":
    main()