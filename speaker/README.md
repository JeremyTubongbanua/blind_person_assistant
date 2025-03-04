# speaker setup

View speakers by

```bash
aplay -l
```

Then change speaker via

```bash
alsamixer -c 3
```

To set volume, use

```bash
amixer -c 3 set PCM 50%
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
espeak-ng -v en-us -s 130 "This is American English at a slower pace"
```

In a Python script:

```py
import subprocess

speed = 150  # Set your desired speed
text = "This is spoken at a custom speed"
subprocess.run(["espeak-ng", "-s", str(speed), text])
```