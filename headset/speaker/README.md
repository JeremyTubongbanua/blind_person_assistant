# speaker setup

View speakers by

```bash
aplay -l
```

Then change speaker via

```bash
alsamixer -c 1
```

To set volume, use

```bash
amixer -c 1 set PCM 80%
```

## espeak-ng

espeak-ng is a lightweight TTS engine

To test espeak-ng, first install it via `sudo apt install -y espeak-ng`

Then test it via

```bash
espeak-ng "This is a test of text to speech on Raspberry Pi"
```

Slow speed:

```bash
espeak-ng -s 120 "This text will be spoken at a slower speed"
```

Fast speed:
```bash
espeak-ng -s 250 "This text will be spoken at a faster speed"
```

American english:

```bash
espeak-ng -v en-us -s 130 "This is American English at a slower pace" --stdout 
```

In a Python script:

```py
import subprocess

speed = 150  # Set your desired speed
text = "This is spoken at a custom speed"
subprocess.run(["espeak-ng", "-s", str(speed), text])
```

## main.py

To test each endpoint,

1. Play an audio file

`curl "http://localhost:5001/play_file?file=jjk.wav"`
`curl "http://localhost:5001/play_file?file=mixkit-retro-game-notification-212.wav"`

2. Set volume to 75%

`curl "http://localhost:5001/set_volume?volume=75"`

3. Get current volume

`curl "http://localhost:5001/get_volume"`

4. Text-to-speech with default settings

`curl "http://localhost:5001/tts?text=Hello%20Raspberry%20Pi"`

5. Text-to-speech with custom settings

`curl "http://localhost:5001/tts?text=This%20is%20a%20fast%20speaking%20voice&speed=250&voice_name=en-us"`
`curl "http://localhost:5001/tts?text=This%20is%20a%20normal%20speaking%20voice&speed=175&voice_name=en-us"`
