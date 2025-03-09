DEFAULT_TTS_SPEED = 175
DEFAULT_TTS_VOICE = "en-us"
DEFAULT_LANGUAGE = "en"
DEFAULT_VOLUME = 80

current_tts_speed = DEFAULT_TTS_SPEED
current_tts_voice = DEFAULT_TTS_VOICE
current_language = DEFAULT_LANGUAGE
current_volume = DEFAULT_VOLUME

current_menu_index = 0

menu_options = [
    "Say Detections",
    "Scan Sign",
    "Track Object",
    "Calibrate Gyros",
    "Volume Settings"
]

def reset_to_defaults():
    global current_tts_speed, current_tts_voice, current_language, current_volume, current_menu_index
    current_tts_speed = DEFAULT_TTS_SPEED
    current_tts_voice = DEFAULT_TTS_VOICE
    current_language = DEFAULT_LANGUAGE
    current_volume = DEFAULT_VOLUME
    current_menu_index = 0

def get_next_menu_index():
    global current_menu_index
    current_menu_index = (current_menu_index + 1) % len(menu_options)
    return current_menu_index

def get_current_menu_option():
    return menu_options[current_menu_index]

def update_tts_speed(speed):
    global current_tts_speed
    current_tts_speed = speed

def update_tts_voice(voice):
    global current_tts_voice
    current_tts_voice = voice

def update_language(language):
    global current_language
    current_language = language

def update_volume(volume):
    global current_volume
    current_volume = volume