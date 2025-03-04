#!/usr/bin/env python3
from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import argparse
import json
import blobconverter
from flask import Flask, Response, request, jsonify
import threading
import paho.mqtt.client as mqtt
import json

app = Flask(__name__)

latest_frame = None
lock = threading.Lock()
last_detection_payload = None
last_detection_time = 0
DETECTION_THROTTLE_SECONDS = 0.5

stream_quality = 50
stream_fps = 5
stream_resolution = (320, 240)

mqtt_client = mqtt.Client()
mqtt_broker = "0.0.0.0"
mqtt_port = 1883
mqtt_topic = "pi4/detections"

def setup_mqtt():
    try:
        mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        mqtt_client.loop_start()
        print(f"Connected to MQTT broker at {mqtt_broker}:{mqtt_port}")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--model", help="Provide model name or model path for inference", type=str)
parser.add_argument("-c", "--config", help="Provide config path for inference", type=str)
parser.add_argument("--mqtt_broker", help="MQTT broker address", type=str, default="0.0.0.0")
parser.add_argument("--mqtt_port", help="MQTT broker port", type=int, default=1883)
parser.add_argument("--mqtt_topic", help="MQTT topic for publishing detections", type=str, default="pi4/detections")
parser.add_argument("--fps", help="Camera FPS", type=int, default=15)
parser.add_argument("--process_every", help="Process only every N frames", type=int, default=1)
args = parser.parse_args()

configPath = Path(args.config)
if not configPath.exists():
    raise ValueError(f"Path {configPath} does not exist!")

with configPath.open() as f:
    config = json.load(f)
nnConfig = config.get("nn_config", {})

if "input_size" in nnConfig:
    W, H = tuple(map(int, nnConfig.get("input_size").split('x')))

metadata = nnConfig.get("NN_specific_metadata", {})
classes = metadata.get("classes", 80)
coordinates = metadata.get("coordinates", 4)
anchors = metadata.get("anchors", [])
anchorMasks = metadata.get("anchor_masks", {})
iouThreshold = metadata.get("iou_threshold", 0.5)
confidenceThreshold = metadata.get("confidence_threshold", 0.5)

nnMappings = config.get("mappings", {})
labels = nnMappings.get("labels", [])

nnPath = Path(args.model)
if not nnPath.exists():
    print(f"No blob found at {nnPath}. Fetching from model zoo.")
    nnPath = blobconverter.from_zoo(args.model, shaves=6, zoo_type="depthai", use_cache=True)
nnPath = str(nnPath)

pipeline = dai.Pipeline()

camRgb = pipeline.create(dai.node.ColorCamera)
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
stereo = pipeline.create(dai.node.StereoDepth)
xoutRgb = pipeline.create(dai.node.XLinkOut)
nnOut = pipeline.create(dai.node.XLinkOut)
xoutDepth = pipeline.create(dai.node.XLinkOut)

xoutRgb.setStreamName("rgb")
nnOut.setStreamName("nn")
xoutDepth.setStreamName("depth")

camRgb.setPreviewSize(W, H)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_720_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(args.fps)

imgManip = pipeline.create(dai.node.ImageManip)
imgManip.initialConfig.setHorizontalFlip(True)
imgManip.initialConfig.setVerticalFlip(True)
imgManip.initialConfig.setResize(W, H)
imgManip.setMaxOutputFrameSize(W * H * 3)

monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)

stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
stereo.setLeftRightCheck(True)
stereo.setSubpixel(False)
stereo.setExtendedDisparity(False)

detectionNetwork.setBlobPath(nnPath)
detectionNetwork.setConfidenceThreshold(confidenceThreshold)
detectionNetwork.setNumClasses(classes)
detectionNetwork.setCoordinateSize(coordinates)
detectionNetwork.setAnchors(anchors)
detectionNetwork.setAnchorMasks(anchorMasks)
detectionNetwork.setIouThreshold(iouThreshold)
detectionNetwork.setNumInferenceThreads(1)
detectionNetwork.input.setBlocking(False)

camRgb.preview.link(imgManip.inputImage)
imgManip.out.link(detectionNetwork.input)

detectionNetwork.passthrough.link(xoutRgb.input)
detectionNetwork.out.link(nnOut.input)

monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)
stereo.depth.link(xoutDepth.input)

def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def draw_detections(frame, detections, depthFrame):
    global last_detection_payload, last_detection_time
    
    color = (255, 0, 0)
    detection_results = []
    
    current_time = time.time()
    should_publish = (current_time - last_detection_time) >= DETECTION_THROTTLE_SECONDS
    
    for detection in detections:
        bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)

        if detection.label < len(labels):
            label_text = labels[detection.label]
        else:
            label_text = f"Label {detection.label}"

        cv2.putText(
            frame,
            label_text,
            (bbox[0] + 10, bbox[1] + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        cv2.putText(
            frame,
            f"{int(detection.confidence * 100)}%",
            (bbox[0] + 10, bbox[1] + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        distance = None
        if depthFrame is not None:
            x1, y1, x2, y2 = bbox
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            sample_size = 20
            x_start = max(center_x - sample_size//2, 0)
            y_start = max(center_y - sample_size//2, 0)
            x_end = min(center_x + sample_size//2, depthFrame.shape[1])
            y_end = min(center_y + sample_size//2, depthFrame.shape[0])
            
            if x_end > x_start and y_end > y_start:
                depth_slice = depthFrame[y_start:y_end, x_start:x_end]
                
                if depth_slice.size > 0:
                    depth_val = np.median(depth_slice)
                    distance = depth_val / 1000.0
                    cv2.putText(
                        frame,
                        f"Dist: {distance:.1f}m",
                        (bbox[0] + 10, bbox[1] + 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1
                    )
        
        detection_data = {
            "label": label_text,
            "confidence": round(float(detection.confidence), 2),
            "bbox": {
                "x1": int(bbox[0]),
                "y1": int(bbox[1]),
                "x2": int(bbox[2]),
                "y2": int(bbox[3])
            },
            "timestamp": int(current_time)
        }
        
        if distance is not None:
            detection_data["distance"] = round(float(distance), 1)
            
        detection_results.append(detection_data)
    
    if detection_results and mqtt_client.is_connected() and should_publish:
        payload = json.dumps({"detections": detection_results})
        
        if last_detection_payload is None or payload != last_detection_payload:
            mqtt_client.publish(mqtt_topic, payload)
            last_detection_payload = payload
            last_detection_time = current_time
        
    return detection_results

def run_pipeline():
    global latest_frame, mqtt_broker, mqtt_port, mqtt_topic
    
    mqtt_broker = args.mqtt_broker
    mqtt_port = args.mqtt_port
    mqtt_topic = args.mqtt_topic
    
    setup_mqtt()
    
    with dai.Device(pipeline) as device:
        qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
        qDepth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)

        startTime = time.monotonic()
        counter = 0
        frame_counter = 0
        depthFrame = None
        detections = []
        process_every = args.process_every
        fps_update_interval = 30

        while True:
            inRgb = qRgb.get()
            
            frame_counter += 1
            if frame_counter % process_every == 0:
                inDet = qDet.tryGet()
                inDepth = qDepth.tryGet()
                
                if inDet is not None:
                    detections = inDet.detections
                    counter += 1

                if inDepth is not None:
                    depthFrame = inDepth.getFrame()

            if inRgb is not None:
                frame = inRgb.getCvFrame()
                
                display_frame = cv2.resize(frame, (640, 360))
                
                if frame_counter % fps_update_interval == 0:
                    current_time = time.monotonic()
                    time_diff = current_time - startTime
                    if time_diff > 0:
                        fps = counter / time_diff
                        if counter > 100:
                            startTime = current_time
                            counter = 0
                    else:
                        fps = 0
                        
                    cv2.putText(
                        display_frame,
                        f"FPS: {fps:.1f}",
                        (2, display_frame.shape[0] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (255, 255, 255)
                    )

                if frame_counter % process_every == 0:
                    draw_detections(display_frame, detections, depthFrame)

                with lock:
                    latest_frame = display_frame

def generate_frames():
    global latest_frame
    last_frame_time = 0
    frame_interval = 1.0 / stream_fps
    
    while True:
        current_time = time.time()
        
        if current_time - last_frame_time < frame_interval:
            time.sleep(0.01)
            continue
            
        with lock:
            if latest_frame is None:
                time.sleep(0.1)
                continue
            small_frame = cv2.resize(latest_frame, stream_resolution)
        
        ret, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, stream_quality])
        if not ret:
            continue

        last_frame_time = current_time
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stream_settings')
def stream_settings():
    global stream_fps, stream_quality, stream_resolution
    
    fps = request.args.get('fps', type=int)
    quality = request.args.get('quality', type=int)
    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)
    
    if fps and 1 <= fps <= 30:
        stream_fps = fps
    if quality and 1 <= quality <= 100:
        stream_quality = quality
    if width and height and width > 0 and height > 0:
        stream_resolution = (width, height)
        
    return jsonify({
        'fps': stream_fps,
        'quality': stream_quality,
        'resolution': stream_resolution
    })

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Stream</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            img { max-width: 100%; border: 1px solid #ddd; }
            .controls { margin: 15px 0; }
            button, select { padding: 5px 10px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <h1>Raspberry Pi Camera Stream</h1>
        <div>
            <img src="/video_stream" alt="Video Stream">
        </div>
        <div class="controls">
            <h3>Stream Settings</h3>
            <div>
                <label for="quality">Quality:</label>
                <select id="quality">
                    <option value="20">Very Low (20%)</option>
                    <option value="40">Low (40%)</option>
                    <option value="60" selected>Medium (60%)</option>
                    <option value="80">High (80%)</option>
                </select>
                
                <label for="fps">FPS:</label>
                <select id="fps">
                    <option value="1">1 FPS</option>
                    <option value="2">2 FPS</option>
                    <option value="5" selected>5 FPS</option>
                    <option value="10">10 FPS</option>
                    <option value="15">15 FPS</option>
                </select>
                
                <label for="resolution">Resolution:</label>
                <select id="resolution">
                    <option value="160x120">160x120</option>
                    <option value="320x240" selected>320x240</option>
                    <option value="640x360">640x360</option>
                    <option value="640x480">640x480</option>
                </select>
                
                <button id="applySettings">Apply</button>
            </div>
        </div>
        
        <script>
            document.getElementById('applySettings').addEventListener('click', function() {
                const quality = document.getElementById('quality').value;
                const fps = document.getElementById('fps').value;
                const resolution = document.getElementById('resolution').value;
                const [width, height] = resolution.split('x');
                
                fetch(`/stream_settings?quality=${quality}&fps=${fps}&width=${width}&height=${height}`)
                    .then(response => response.json())
                    .then(data => {
                        console.log('Settings updated:', data);
                        alert('Stream settings updated!');
                    });
            });
        </script>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    app.run(host='0.0.0.0', port=8005, debug=False, threaded=True)
