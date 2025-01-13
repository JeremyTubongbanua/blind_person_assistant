#!/usr/bin/env python3

import depthai as dai
from flask import Flask, Response
import cv2

app = Flask(__name__)

# Initialize the DepthAI pipeline
pipeline = dai.Pipeline()
cam = pipeline.createColorCamera()
cam.setPreviewSize(640, 480)
cam.setFps(30)
xout = pipeline.createXLinkOut()
xout.setStreamName("video")
cam.preview.link(xout.input)

# Start the device
device = dai.Device(pipeline)
video_queue = device.getOutputQueue(name="video", maxSize=4, blocking=False)

def generate_frames():
    while True:
        frame = video_queue.get().getCvFrame()
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
