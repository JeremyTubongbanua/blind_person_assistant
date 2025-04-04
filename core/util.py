import asyncio
import requests
from googletrans import Translator

def vibrate_cane_motors(left_duration=0, right_duration=0):
    VIBRATION_URL = "http://localhost:5000/vibrate"
    try:
        payload = {
            "left_duration": left_duration,
            "right_duration": right_duration
        }
        response = requests.post(VIBRATION_URL, json=payload)
        if response.status_code != 200:
            print(f"Vibration request failed with status code {response.status_code}")
    except Exception as e:
        print(f"Error sending vibration request: {e}")

def send_tts(text, speed=None, voice_name=None):
    TTS_URL = "http://localhost:5001/tts"
    if speed is None:
        speed = 150
    if voice_name is None:
        voice_name = 'en-US'
        
    try:
        if voice_name.lower() == "fr-fr":
            try:
                translator = Translator()
                
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                translated = loop.run_until_complete(translator.translate(text, dest='fr'))
                
                text = translated.text
                print(f"Translated to French: {text}")
            except Exception as e:
                print(f"Translation error: {e}, using original text")
            
        url = f"{TTS_URL}?text={text}&speed={speed}&voice_name={voice_name}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"TTS request failed with status code {response.status_code}")
    except Exception as e:
        print(f"Error sending TTS request: {e}")
        
def camera_detections():
    CAMERA_DETECTIONS_ENDPOINT = 'http://localhost:8005/detections'
    response = requests.get(CAMERA_DETECTIONS_ENDPOINT)
    return response

def zero_pyr_headset():
    ENDPOINT = 'http://localhost:5002/zero'
    response = requests.post(ENDPOINT)
    return response

def zero_pyr_cane():
    ENDPOINT = 'http://192.168.2.219:5002/zero'
    response = requests.post(ENDPOINT)
    return response