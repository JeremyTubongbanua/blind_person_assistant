#!/bin/bash
h="192.168.8.220"
echo http://$h:8005/video_stream
sudo python3 camera_stream.py -m yolov8ntrained_openvino_2022.1_6shave.blob -c yolov8ntrained.json
