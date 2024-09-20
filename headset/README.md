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
