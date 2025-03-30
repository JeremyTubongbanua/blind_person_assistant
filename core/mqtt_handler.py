import paho.mqtt.client as mqtt
import json
import sys
import io
import time

class MqttHandler:
    def __init__(self, broker, port, button_topic, menu_logs_topic="pi4/menu_logs", menu_topic="pi4/menu"):
        self.broker = broker
        self.port = port
        self.button_topic = button_topic
        self.menu_logs_topic = menu_logs_topic
        self.menu_topic = menu_topic
        self.mqtt_client = None
        
        # Setup stdout redirection to capture prints
        self.original_stdout = sys.stdout
        self.stdout_capture = io.StringIO()
        sys.stdout = self
        
    def write(self, text):
        # Write to the original stdout
        self.original_stdout.write(text)
        self.original_stdout.flush()
        
        # Also capture the text
        self.stdout_capture.write(text)
        
        # Publish log message if we have complete lines
        if '\n' in text:
            lines = self.stdout_capture.getvalue().split('\n')
            # Keep the last line if it doesn't end with newline
            if lines[-1]:
                self.stdout_capture = io.StringIO()
                self.stdout_capture.write(lines[-1])
                lines = lines[:-1]
            else:
                self.stdout_capture = io.StringIO()
                lines = lines[:-1]  # Remove the empty string after the last newline
                
            # Publish each complete line
            for line in lines:
                if line.strip():  # Only publish non-empty lines
                    self.publish_log(line)
    
    def flush(self):
        self.original_stdout.flush()
    
    def __del__(self):
        # Restore stdout when the object is deleted
        sys.stdout = self.original_stdout

    def connect(self, on_connect_callback, on_message_callback):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect_callback
        client.on_message = on_message_callback

        try:
            client.connect(self.broker, self.port, 60)
            self.mqtt_client = client
            return client
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")
            return None

    def publish_log(self, message):
        if self.mqtt_client:
            try:
                self.mqtt_client.publish(self.menu_logs_topic, json.dumps({"message": message}))
            except Exception as e:
                self.original_stdout.write(f"Error publishing log to MQTT: {e}\n")
                self.original_stdout.flush()
        
        # Avoid recursive logging when writing to stdout
        if sys.stdout is self:
            self.original_stdout.write(f"{message}\n")
            self.original_stdout.flush()

    def publish_menu(self, menu_structure):
        if not self.mqtt_client:
            return

        try:
            # Convert to JSON for proper parsing on the dashboard
            menu_data = {
                "structure": menu_structure,
                "timestamp": time.time()
            }
            self.mqtt_client.publish(self.menu_topic, json.dumps(menu_data))
        except Exception as e:
            print(f"Error publishing menu structure: {e}")

    def format_menu_structure(self, current_menu, current_menu_index, menu_items, menu_history):
        # Create a structure that will be easily displayed on the dashboard
        menu_data = {
            "current_menu": current_menu,
            "current_index": current_menu_index,
            "items": [],
            "history": [{"menu": menu, "index": index} for menu, index in menu_history],
            "path": []
        }
        
        # Format the menu items
        for i, item in enumerate(menu_items):
            menu_data["items"].append({
                "name": item["name"],
                "is_selected": (i == current_menu_index),
                "has_submenu": "submenu" in item,
                "has_action": "action" in item
            })
        
        # Create a path string
        path = []
        for menu, _ in menu_history:
            path.append(menu)
        path.append(current_menu)
        menu_data["path"] = path
        
        return json.dumps(menu_data)