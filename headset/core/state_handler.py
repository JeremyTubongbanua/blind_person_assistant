import json
import os

class StateHandler:
    def __init__(self, state_file='state.json'):
        self.state_file = state_file
        self.state = {}
        
    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            else:
                self.state = {}
                self.save_state()
        except Exception as e:
            print(f"Error loading state: {e}")
            self.state = {}
            
    def save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
            
    def get_state(self, key, default=None):
        return self.state.get(key, default)
        
    def set_state(self, key, value):
        self.state[key] = value