# headset

## Darkice

Followed this tutorial: <https://www.youtube.com/watch?v=B9Iom7kNr74&t=605s>

```bash
sudo apt-get update
sudo apt-get install -y icecast2
sudo apt-get install -y darkice
```

Set up config file

```bash
sudo nano /etc/darkice.cfg
```

```bash
[general]
duration = 0
bufferSecs = 5
reconnect = yes

[input]
device = plughw:1,0
sampleRate = 44100
bitsPerSample = 16
channel = 2

[icecast2-0]
bitrateMode = cbr
format = mp3
bitrate = 128
server = localhost
port = 8000
password = 123
mountPoint = mystream
name = My Stream
description = My Stream Description
url = http://localhost
genre = My Stream Genre
public = no
```

Now it is open on 192.168.8.214:8000/mystream

We can also set up a systemd service

```bash
sudo nano /etc/systemd/system/darkice.service
```

```bash
[Unit]
Description=DarkIce Streaming Service
After=network.target sound.target

[Service]
ExecStart=/usr/bin/darkice
WorkingDirectory=/home/jeremy
User=jeremy
Group=audio
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable darkice
sudo systemctl start darkice
```

## video_stream.py

Python code to output video stream to 192.168.8.214:8001/video_stream

```py
#!/usr/bin/env python3s
import cv2
from flask import Flask, Response

app = Flask(__name__)

camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
```

To run,

```bash
chmod +x video_stream.py
./video_stream.py
```

### Systemd

```bash
sudo nano /etc/systemd/system/video_stream.service
```

```bash
[Unit]
Description=USB Camera Video Streaming Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/jeremy/headset/video_stream.py
WorkingDirectory=/home/jeremy/headset
User=jeremy
Group=video
Restart=always
Environment=DISPLAY=:0
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable video_stream
sudo systemctl start video_stream
```

## audio_stream.py

To send a wav file to play

```bash
curl -X POST http://192.168.8.214:8002/play -F "file=@/Users/jeremytubongbanua/Desktop/file.wav" -F "volume=100"
```

Python Code

```py
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

```

To set volume, use

```bash
alsamixer
```

or

```bash
amixer set PCM 100%
```

To stop the audio

```bash
curl -X POST http://192.168.8.214:8002/stop
```
