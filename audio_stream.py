#!/usr/bin/env python3

from flask import Flask, request, jsonify
import pygame
import os
import time
import threading

app = Flask(__name__)
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

pygame.mixer.init(frequency=44100, size=-16, channels=2)

def play_audio(file_path, volume):
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.set_volume(volume)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(1)

@app.route('/play', methods=['POST'])
def play():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not (file.filename.lower().endswith('.mp3') or file.filename.lower().endswith('.wav')):
            return jsonify({'error': 'Unsupported file type, only .mp3 and .wav allowed'}), 400

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        volume = request.form.get('volume', default=50, type=int)
        volume = max(0, min(volume, 100)) / 100

        threading.Thread(target=play_audio, args=(file_path, volume)).start()

        return jsonify({'message': f'Playing {file.filename} with volume {volume * 100}%'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop():
    try:
        pygame.mixer.music.stop()
        return jsonify({'message': 'Playback stopped'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
