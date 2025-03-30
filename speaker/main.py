from flask import Flask, request, jsonify
import os
import pygame
import subprocess
import re
import tempfile
import threading
from time import sleep

app = Flask(__name__)

VOLUME_CONTROL = "PCM"
AUDIO_FILES_DIR = "files"
DEFAULT_VOICE = "en-us"
DEFAULT_SPEED = 100

playback_active = False
playback_lock = threading.Lock()

def detect_usb_speaker():
    global CARD_NUMBER
    
    try:
        output = subprocess.check_output("aplay -l", shell=True).decode('utf-8')
        print("Detected audio devices:")
        print(output)
        
        usb_card = None
        for line in output.split('\n'):
            if "USB Audio" in line:
                match = re.search(r'card (\d+):', line)
                if match:
                    usb_card = int(match.group(1))
                    break
        
        if usb_card is not None:
            CARD_NUMBER = usb_card
            print(f"USB Audio device detected on card {CARD_NUMBER}")
            os.environ["SDL_AUDIODRIVER"] = "alsa"
            os.environ["AUDIODEV"] = f'plughw:{CARD_NUMBER},0'
            return True
        else:
            print("No USB audio device found, using default card 1")
            CARD_NUMBER = 1
            os.environ["SDL_AUDIODRIVER"] = "alsa"
            os.environ["AUDIODEV"] = f'plughw:{CARD_NUMBER},0'
            return False
    except Exception as e:
        print(f"Error detecting USB speaker: {e}")
        print("Using default card 1")
        CARD_NUMBER = 1
        os.environ["SDL_AUDIODRIVER"] = "alsa"
        os.environ["AUDIODEV"] = f'plughw:{CARD_NUMBER},0'
        return False

def get_current_volume():
    try:
        cmd = f"amixer -c {CARD_NUMBER} get {VOLUME_CONTROL}"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8')
        
        match = re.search(r'(\d+)%', output)
        if match:
            return int(match.group(1))
        return 0
    except Exception as e:
        print(f"Error getting volume: {e}")
        return 0

def set_system_volume(volume_percent):
    try:
        volume_percent = max(0, min(100, volume_percent))
        cmd = f"amixer -c {CARD_NUMBER} set {VOLUME_CONTROL} {volume_percent}%"
        subprocess.run(cmd, shell=True, check=True)
        return True
    except Exception as e:
        print(f"Error setting volume: {e}")
        return False

def stop_playback():
    global playback_active
    
    with playback_lock:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        playback_active = False

def play_audio_file(file_path, volume_scale=1.0):
    global playback_active
    
    try:
        with playback_lock:
            playback_active = True
        
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        else:
            pygame.mixer.music.stop()
        
        volume_scale = max(0.0, min(1.0, volume_scale))
        pygame.mixer.music.set_volume(volume_scale)
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy() and playback_active:
            pygame.time.Clock().tick(10)
            
        return True
    except Exception as e:
        print(f"Error playing audio: {e}")
        return False
    finally:
        with playback_lock:
            playback_active = False

def text_to_speech(text, speed=DEFAULT_SPEED, voice=DEFAULT_VOICE):
    try:
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_file.close()
        
        cmd = f'espeak-ng -v {voice} -s {speed} -w {temp_file.name} "{text}"'
        subprocess.run(cmd, shell=True, check=True)
        
        return temp_file.name
    except Exception as e:
        print(f"Error generating speech: {e}")
        return None

@app.route('/play_file', methods=['GET'])
def api_play_file():
    stop_playback()
    
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({"error": "Missing file parameter"}), 400
    
    file_path = os.path.join(AUDIO_FILES_DIR, file_name)
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"File not found: {file_path}"}), 404
    
    volume_scale = get_current_volume() / 100.0
    
    playback_thread = threading.Thread(
        target=play_audio_file, 
        args=(file_path, volume_scale),
        daemon=True
    )
    playback_thread.start()
    
    return jsonify({
        "message": f"Started playing file: {file_name}", 
        "volume": get_current_volume()
    })

@app.route('/set_volume', methods=['GET'])
def api_set_volume():
    volume_str = request.args.get('volume')
    if not volume_str:
        return jsonify({"error": "Missing volume parameter"}), 400
    
    try:
        volume = int(volume_str)
        success = set_system_volume(volume)
        
        if success:
            current_volume = get_current_volume()
            
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(current_volume / 100.0)
                
            return jsonify({
                "message": f"Volume set to {current_volume}%", 
                "volume": current_volume
            })
        else:
            return jsonify({"error": "Failed to set volume"}), 500
    except ValueError:
        return jsonify({"error": "Volume must be a number"}), 400

@app.route('/get_volume', methods=['GET'])
def api_get_volume():
    volume = get_current_volume()
    return jsonify({"volume": volume})

@app.route('/tts', methods=['GET'])
def api_text_to_speech():
    stop_playback()
    
    text = request.args.get('text')
    if not text:
        return jsonify({"error": "Missing text parameter"}), 400
    
    speed = request.args.get('speed', DEFAULT_SPEED)
    voice = request.args.get('voice_name', DEFAULT_VOICE)
    
    try:
        speed = int(speed)
        
        audio_file = text_to_speech(text, speed, voice)
        if not audio_file:
            return jsonify({"error": "Failed to generate speech"}), 500
        
        volume_scale = get_current_volume() / 100.0
        
        def play_and_cleanup():
            try:
                play_audio_file(audio_file, volume_scale)
            finally:
                try:
                    os.unlink(audio_file)
                except:
                    pass
        
        playback_thread = threading.Thread(
            target=play_and_cleanup,
            daemon=True
        )
        playback_thread.start()
        
        return jsonify({
            "message": "Started text-to-speech playback",
            "text": text,
            "speed": speed,
            "voice": voice,
            "volume": get_current_volume()
        })
    except ValueError:
        return jsonify({"error": "Speed must be a number"}), 400

@app.route('/stop', methods=['GET'])
def api_stop_playback():
    stop_playback()
    return jsonify({"message": "Playback stopped"})

@app.route('/card_info', methods=['GET'])
def api_card_info():
    try:
        output = subprocess.check_output("aplay -l", shell=True).decode('utf-8')
        return jsonify({
            "card_number": CARD_NUMBER,
            "audio_devices": output,
            "volume": get_current_volume()
        })
    except Exception as e:
        return jsonify({"error": f"Error getting card info: {e}"}), 500

if __name__ == '__main__':
    sleep(1)
    os.makedirs(AUDIO_FILES_DIR, exist_ok=True)
    
    detect_usb_speaker()
    
    pygame.mixer.init()
    
    print(f"Using audio card {CARD_NUMBER}")
    play_audio_file('files/mixkit-retro-game-notification-212.wav')
    
    app.run(host='0.0.0.0', port=5001, debug=False)