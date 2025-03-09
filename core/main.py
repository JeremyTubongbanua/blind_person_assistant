import requests
import json
import time
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

prev_button1 = False
prev_button2 = False

running = True

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

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    send_tts("Menu system connected. Use button 2 to cycle through options, button 1 to select.")

def on_message(client, userdata, msg):
    global button_state, prev_button1, prev_button2
    
    try:
        payload = json.loads(msg.payload.decode())
        
        prev_button1 = button_state["button1"]
        prev_button2 = button_state["button2"]
        
        button_state = payload
        
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
    pass

def scan_sign():
    send_tts("Scanning sign")
    pass

def track_object():
    send_tts("Tracking object")
    pass

def calibrate_gyros():
    send_tts("Calibrating gyros")
    pass

def volume_settings():
    send_tts("Adjusting volume settings")
    pass

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
    client = init_mqtt()
    if client is None:
        print("Failed to initialize MQTT client. Exiting.")
        return
    
    client.loop_start()
    
    option_index = state.current_menu_index + 1
    current_option = state.get_current_menu_option()
    send_tts(f"Menu system initialized.")
    send_tts(f"Current menu option: {option_index}: {current_option}")
    
    try:
        while running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Exiting menu system")

if __name__ == "__main__":
    main()