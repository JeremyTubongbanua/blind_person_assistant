import requests
import json
import time
import threading
import queue
import paho.mqtt.client as mqtt
import state

TTS_URL = "192.168.2.220:5001/tts"
MQTT_BROKER = "192.168.2.219"
MQTT_PORT = 1883
MQTT_TOPIC = "pi2/button_state"

button_state = {
    "button1": False,
    "button2": False,
    "timestamp": 0
}

button_event_queue = queue.Queue()
button_subscribers = []
running = True
in_submenu = False

def button_event_worker():
    global running
    while running:
        try:
            event_data = button_event_queue.get(timeout=0.5)
            if event_data:
                button, event = event_data
                print(f"Processing event: {button} {event}")
                for subscriber in button_subscribers:
                    if subscriber:
                        try:
                            subscriber(button, event)
                        except Exception as e:
                            print(f"Error in button subscriber: {e}")
            button_event_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in button event worker: {e}")

def send_tts(text, speed=None, voice_name=None):
    if speed is None:
        speed = state.current_tts_speed
    if voice_name is None:
        voice_name = state.current_tts_voice
    
    params = {
        "text": text,
        "speed": speed,
        "voice_name": voice_name
    }
    
    try:
        url = f"http://{TTS_URL}"
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"TTS request failed with status code {response.status_code}")
    except Exception as e:
        print(f"Error sending TTS request: {e}")

def subscribe_to_buttons(callback):
    button_subscribers.append(callback)
    return len(button_subscribers) - 1

def unsubscribe_from_buttons(subscriber_id):
    if 0 <= subscriber_id < len(button_subscribers):
        button_subscribers[subscriber_id] = None

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    send_tts("Menu system connected. Use button 2 to cycle through options, button 1 to select.")

def on_message(client, userdata, msg):
    global button_state
    
    try:
        payload = json.loads(msg.payload.decode())
        
        prev_button1 = button_state["button1"]
        prev_button2 = button_state["button2"]
        
        button_state = payload
        
        print(f"MQTT: B1: {prev_button1}->{button_state['button1']}, B2: {prev_button2}->{button_state['button2']}")
        
        if button_state["button1"] and not prev_button1:
            print("Queuing button1 pressed event")
            button_event_queue.put(("button1", "pressed"))
        elif not button_state["button1"] and prev_button1:
            print("Queuing button1 released event")
            button_event_queue.put(("button1", "released"))
            
        if button_state["button2"] and not prev_button2:
            print("Queuing button2 pressed event")
            button_event_queue.put(("button2", "pressed"))
        elif not button_state["button2"] and prev_button2:
            print("Queuing button2 released event")
            button_event_queue.put(("button2", "released"))
        
        if not in_submenu:
            if button_state["button2"] and not prev_button2:
                cycle_menu()
            
            if button_state["button1"] and not prev_button1:
                select_current_option()
            
    except json.JSONDecodeError:
        print(f"Error decoding JSON: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")

def cycle_menu():
    state.get_next_menu_index()
    current_option = state.get_current_menu_option()
    option_index = state.current_menu_index + 1
    send_tts(f"option {option_index}: {current_option}")
    print(f"Current menu option: {option_index}: {current_option}")

def select_current_option():
    current_option = state.get_current_menu_option()
    option_index = state.current_menu_index + 1
    send_tts(f"Selected option {option_index}: {current_option}")
    print(f"Selected option {option_index}: {current_option}")
    
    option_index = state.current_menu_index
    
    if option_index == 0:
        say_detections()
    elif option_index == 1:
        scan_sign()
    elif option_index == 2:
        track_object()
    elif option_index == 3:
        calibrate_gyros()
    elif option_index == 4:
        volume_settings()

def say_detections():
    send_tts("Saying detections")

def scan_sign():
    send_tts("Scanning sign")

def track_object():
    send_tts("Tracking object")

def calibrate_gyros():
    send_tts("Calibrating gyros")

def volume_settings():
    global running, in_submenu, button_state
    
    print("Entering volume settings")
    send_tts("Adjusting volume settings")
    
    try:
        response = requests.get(f"http://localhost:5001/get_volume")
        if response.status_code == 200:
            current_volume = response.json().get('volume', 50)
        else:
            current_volume = 50
    except Exception as e:
        print(f"Error getting volume: {e}")
        current_volume = 50
    
    print(f"Current volume: {current_volume}")
    send_tts(f"Current volume {current_volume}")
    
    volume_lock = threading.Lock()
    volume_changed = False
    last_change_time = time.time()
    last_announcement = time.time()
    
    print("Clearing any pending button events")
    while not button_event_queue.empty():
        try:
            button_event_queue.get(block=False)
            button_event_queue.task_done()
        except:
            pass
    
    in_submenu = True
    
    print("Forcing button state reset")
    button_state = {
        "button1": False,
        "button2": False,
        "timestamp": time.time()
    }
    
    time.sleep(0.5)
    
    print(f"Current button state: B1: {button_state['button1']}, B2: {button_state['button2']}")
    
    volume_button_state = {
        "button1": False,
        "button2": False
    }
    
    def handle_volume_buttons():
        nonlocal current_volume, volume_changed, last_change_time, last_announcement
        nonlocal volume_button_state
        
        curr_b1 = button_state["button1"]
        curr_b2 = button_state["button2"]
        
        b1_pressed = curr_b1 and not volume_button_state["button1"]
        b2_pressed = curr_b2 and not volume_button_state["button2"]
        
        if b1_pressed:
            current_volume = max(0, current_volume - 5)
            print(f"Volume decreased to {current_volume}%")
            
            if time.time() - last_announcement > 0.5:
                send_tts(f"Volume {current_volume}")
                last_announcement = time.time()
            
            volume_changed = True
            last_change_time = time.time()
        
        if b2_pressed:
            current_volume = min(100, current_volume + 5)
            print(f"Volume increased to {current_volume}%")
            
            if time.time() - last_announcement > 0.5:
                send_tts(f"Volume {current_volume}")
                last_announcement = time.time()
            
            volume_changed = True
            last_change_time = time.time()
        
        volume_button_state["button1"] = curr_b1
        volume_button_state["button2"] = curr_b2
    
    try:
        print("Starting volume control loop")
        while running and in_submenu:
            handle_volume_buttons()
            
            with volume_lock:
                if volume_changed and time.time() - last_change_time > 5:
                    print(f"Setting volume to {current_volume}%")
                    try:
                        response = requests.get(f"http://localhost:5001/set_volume?volume={current_volume}")
                        print(f"Volume set response: {response.status_code}")
                    except Exception as e:
                        print(f"Error setting volume: {e}")
                    
                    send_tts(f"Volume set to {current_volume}")
                    time.sleep(0.5)
                    print("Returning to main menu")
                    send_tts("Returning to menu")
                    break
            
            time.sleep(0.1)
    finally:
        print("Exiting volume settings")
        in_submenu = False

def init_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        return client
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return None

def main():
    global running
    
    client = init_mqtt()
    if client is None:
        print("Failed to initialize MQTT client. Exiting.")
        return
    
    print("Starting button event worker thread")
    event_thread = threading.Thread(target=button_event_worker, daemon=True)
    event_thread.start()
    
    client.loop_start()
    
    option_index = state.current_menu_index + 1
    current_option = state.get_current_menu_option()
    send_tts(f"Menu system initialized.")
    send_tts(f"Current menu option: {option_index}: {current_option}")
    
    try:
        print("Entering main loop")
        while running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        running = False
        event_thread.join(timeout=1.0)
        client.loop_stop()
        client.disconnect()
        print("Exiting menu system")

if __name__ == "__main__":
    main()