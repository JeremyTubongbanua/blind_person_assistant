import paho.mqtt.client as mqtt
import json

class MqttHandler:
    def __init__(self, broker, port, button_topic, menu_logs_topic="pi4/menu_logs", menu_topic="pi4/menu"):
        self.broker = broker
        self.port = port
        self.button_topic = button_topic
        self.menu_logs_topic = menu_logs_topic
        self.menu_topic = menu_topic
        self.mqtt_client = None

    def connect(self, on_connect_callback, on_message_callback):
        client = mqtt.Client()
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
            self.mqtt_client.publish(self.menu_logs_topic, message)
        print(message)

    def publish_menu(self, menu_structure):
        if not self.mqtt_client:
            return

        self.mqtt_client.publish(self.menu_topic, menu_structure)

    def format_menu_structure(self, current_menu, current_menu_index, menu_items, menu_history):
        menu_repr = []

        for i, item in enumerate(menu_items):
            if i == current_menu_index:
                menu_repr.append(f"{item['name']} <-")
            else:
                menu_repr.append(item['name'])

        menu_text = "\n".join(menu_repr)

        path = []
        for menu, _ in menu_history:
            path.append(menu)
        path.append(current_menu)

        menu_path = " > ".join(path)
        full_menu = f"{menu_path}\n\n{menu_text}"

        return full_menu