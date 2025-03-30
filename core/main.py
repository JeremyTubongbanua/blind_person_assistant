import requests
import json
import time
import threading
import queue
import paho.mqtt.client as mqtt
from menu_handlers import *

def change_tts_speed():
    print_and_publish("TTS Speed Change function called", None)

def change_tts_language():
    print_and_publish("TTS Language Change function called", None)

TTS_URL = "http://localhost:5001/tts"
MQTT_BROKER = "192.168.2.219"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/button_state"

def print_and_publish(message, mqtt_client=None):
    print(message)
    if mqtt_client:
        mqtt_client.publish("pi4/menu_logs", message)

class MenuSystem:
    def __init__(self):
        self.button_state = {"button1": False, "button2": False, "timestamp": 0}
        self.button_event_queue = queue.Queue()
        self.button_subscribers = []
        self.running = True
        self.in_menu = True
        self.current_menu = "main"
        self.current_menu_index = 0
        self.tts_speed = 1.0
        self.tts_voice = "en-US-Neural2-F"
        self.tts_language = "en-US"
        self.mqtt_client = None
        
        self.menus = {
            "main": [
                {"name": "Announce Detections", "action": announce_detections},
                {"name": "Scan Sign", "action": scan_sign},
                {"name": "Track Object", "action": track_object},
                {"name": "Object Avoidance", "action": object_avoidance},
                {"name": "Gyro Settings", "submenu": "gyro"},
                {"name": "Camera Settings", "submenu": "camera"},
                {"name": "Volume Settings", "submenu": "volume"},
                {"name": "TTS Settings", "submenu": "tts"},
            ],
            "gyro": [
                {"name": "Calibrate Gyros", "action": calibrate_gyros},
                {"name": "Narrate Gyro Values", "action": narrate_gyro_values},
                {"name": "Narrate Pitch Yaw Roll", "action": narrate_pitch_yaw_roll},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "camera": [
                {"name": "Start Camera", "action": start_camera},
                {"name": "Stop Camera", "action": stop_camera},
                {"name": "Restart Camera", "action": restart_camera},
                {"name": "Camera Status", "action": camera_status},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "volume": [
                {"name": "Get Volume", "action": get_volume},
                {"name": "Decrease Volume by 10", "action": decrease_volume},
                {"name": "Increase Volume by 10", "action": increase_volume},
                {"name": "Mute Speaker", "action": mute_speaker},
                {"name": "Back to Main Menu", "submenu": "main"}
            ],
            "tts": [
                {"name": "Change Text To Speech Speed", "action": change_tts_speed},
                {"name": "Change Text To Speech Language", "action": change_tts_language},
                {"name": "Back to Main Menu", "submenu": "main"}
            ]
        }
        
        self.menu_history = []

    def publish_menu_structure(self):
        if not self.mqtt_client:
            return
            
        current_items = self.get_current_menu_items()
        menu_repr = []
        
        for i, item in enumerate(current_items):
            if i == self.current_menu_index:
                menu_repr.append(f"{item['name']} <-")
            else:
                menu_repr.append(item['name'])
        
        menu_text = "\n".join(menu_repr)
        
        path = []
        for menu, _ in self.menu_history:
            path.append(menu)
        path.append(self.current_menu)
        
        menu_path = " > ".join(path)
        full_menu = f"{menu_path}\n\n{menu_text}"
        
        self.mqtt_client.publish("pi4/menu", full_menu)

    def send_tts(self, text, speed=150, voice_name='en-us'):                
        try:
            url = f"{TTS_URL}?text={text}&speed={speed}&voice_name={voice_name}"
            response = requests.get(url)
            if response.status_code != 200:
                print_and_publish(f"TTS request failed with status code {response.status_code}", self.mqtt_client)
        except Exception as e:
            print_and_publish(f"Error sending TTS request: {e}", self.mqtt_client)

    def button_event_worker(self):
        while self.running:
            try:
                event_data = self.button_event_queue.get(timeout=0.5)
                if event_data:
                    button, event = event_data
                    print_and_publish(f"Processing event: {button} {event}", self.mqtt_client)
                    for subscriber in self.button_subscribers:
                        if subscriber:
                            try:
                                subscriber(button, event)
                            except Exception as e:
                                print_and_publish(f"Error in button subscriber: {e}", self.mqtt_client)
                self.button_event_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print_and_publish(f"Error in button event worker: {e}", self.mqtt_client)

    def subscribe_to_buttons(self, callback):
        self.button_subscribers.append(callback)
        return len(self.button_subscribers) - 1

    def unsubscribe_from_buttons(self, subscriber_id):
        if 0 <= subscriber_id < len(self.button_subscribers):
            self.button_subscribers[subscriber_id] = None

    def on_connect(self, client, userdata, flags, rc):
        print_and_publish(f"Connected with result code {rc}", client)
        client.subscribe(MQTT_TOPIC)
        self.send_tts("Menu system connected. Use button 2 to cycle through options, button 1 to select.")
        self.publish_menu_structure()

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            prev_button1 = self.button_state["button1"]
            prev_button2 = self.button_state["button2"]
            
            self.button_state = payload
            
            print_and_publish(f"MQTT: B1: {prev_button1}->{self.button_state['button1']}, B2: {prev_button2}->{self.button_state['button2']}", client)
            
            if self.button_state["button1"] and not prev_button1:
                print_and_publish("Queuing button1 pressed event", client)
                self.button_event_queue.put(("button1", "pressed"))
                if self.in_menu:
                    self.select_current_option()
            elif not self.button_state["button1"] and prev_button1:
                print_and_publish("Queuing button1 released event", client)
                self.button_event_queue.put(("button1", "released"))
                
            if self.button_state["button2"] and not prev_button2:
                print_and_publish("Queuing button2 pressed event", client)
                self.button_event_queue.put(("button2", "pressed"))
                if self.in_menu:
                    self.cycle_menu()
            elif not self.button_state["button2"] and prev_button2:
                print_and_publish("Queuing button2 released event", client)
                self.button_event_queue.put(("button2", "released"))
            
        except json.JSONDecodeError:
            print_and_publish(f"Error decoding JSON: {msg.payload}", client)
        except Exception as e:
            print_and_publish(f"Error processing message: {e}", client)

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
        print_and_publish(f"Current menu option: {option_index}: {current_option}", self.mqtt_client)
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
        print_and_publish(f"Selected option {option_index}: {current_option}", self.mqtt_client)
        
        if "submenu" in current_item:
            submenu = current_item["submenu"]
            self.menu_history.append((self.current_menu, self.current_menu_index))
            self.current_menu = submenu
            self.current_menu_index = 0
            new_option = self.get_current_menu_option()
            new_index = self.current_menu_index + 1
            self.send_tts(f"Submenu {submenu}. option {new_index}: {new_option}")
            print_and_publish(f"Entered submenu {submenu}. Current option {new_index}: {new_option}", self.mqtt_client)
            self.publish_menu_structure()
        elif "action" in current_item:
            action = current_item["action"]
            if action:
                try:
                    self.in_menu = False
                    action()
                    self.in_menu = True
                except Exception as e:
                    print_and_publish(f"Error executing action: {e}", self.mqtt_client)
                    self.send_tts(f"Error executing action")
                    self.in_menu = True

    def init_mqtt(self):
        client = mqtt.Client()
        client.on_connect = lambda client, userdata, flags, rc: self.on_connect(client, userdata, flags, rc)
        client.on_message = lambda client, userdata, msg: self.on_message(client, userdata, msg)
        
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client = client
            return client
        except Exception as e:
            print_and_publish(f"Error connecting to MQTT broker: {e}", None)
            return None

    def run(self):
        client = self.init_mqtt()
        if client is None:
            print_and_publish("Failed to initialize MQTT client. Exiting.", None)
            return
        
        print_and_publish("Starting button event worker thread", client)
        event_thread = threading.Thread(target=self.button_event_worker, daemon=True)
        event_thread.start()
        
        client.loop_start()
        
        current_option = self.get_current_menu_option()
        option_index = self.current_menu_index + 1
        self.send_tts(f"Menu system initialized.")
        self.send_tts(f"Current menu option {option_index}: {current_option}")
        self.publish_menu_structure()
        
        try:
            print_and_publish("Entering main loop", client)
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print_and_publish("Interrupted by user", client)
        finally:
            self.running = False
            event_thread.join(timeout=1.0)
            client.loop_stop()
            client.disconnect()
            print_and_publish("Exiting menu system", None)

def main():
    menu_system = MenuSystem()
    menu_system.run()

if __name__ == "__main__":
    main()