#!/usr/bin/env python3

import cv2
import numpy as np
import time
import depthai as dai
import argparse
from pathlib import Path
import threading
from flask import Flask, Response, render_template_string
import logging

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--display', action='store_true', 
                    help='Display video feed locally (requires display)')
parser.add_argument('-t', '--threshold', type=float, default=0.5, 
                    help='Detection confidence threshold (0-1)')
parser.add_argument('-o', '--output', type=str, 
                    help='Output directory for saving detection images')
parser.add_argument('-p', '--port', type=int, default=3030,
                    help='Web server port (default: 3030)')
args = parser.parse_args()

# Disable Flask's default logging to avoid cluttering the console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Initialize Flask app for web streaming
app = Flask(__name__)

# Global variables for the latest frame and detection results
latest_frame = None
latest_detections = []
frame_lock = threading.Lock()

# HTML template for the streaming page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>OAK-D People Detection</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background-color: #f0f0f0; text-align: center; }
        h1 { color: #333; }
        .video-container { margin: 20px auto; max-width: 90%; }
        img { max-width: 100%; border: 3px solid #ccc; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>OAK-D Lite People Detection</h1>
    <div class="video-container">
        <img src="/video_feed" />
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def generate_frames():
    global latest_frame, latest_detections
    while True:
        with frame_lock:
            if latest_frame is not None:
                frame_with_detections = latest_frame.copy()
                for detection in latest_detections:
                    if detection.label == person_class_id:  # Only show person detections
                        bbox = frameNorm(frame_with_detections, 
                                        (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                        cv2.rectangle(frame_with_detections, (bbox[0], bbox[1]), (bbox[2], bbox[3]), 
                                    (0, 255, 0), 2)
                        cv2.putText(frame_with_detections, f"Person: {detection.confidence:.2f}", 
                                (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                person_count = sum(1 for d in latest_detections if d.label == person_class_id)
                cv2.putText(frame_with_detections, 
                            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')} | People: {person_count}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                ret, buffer = cv2.imencode('.jpg', frame_with_detections)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03)  # ~30 FPS

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

def setup_oak_pipeline():
    pipeline = dai.Pipeline()

    camRgb = pipeline.create(dai.node.ColorCamera)
    detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    nnOut = pipeline.create(dai.node.XLinkOut)

    xoutRgb.setStreamName("rgb")
    nnOut.setStreamName("nn")

    camRgb.setPreviewSize(416, 416)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

    detectionNetwork.setConfidenceThreshold(args.threshold)
    detectionNetwork.setNumClasses(80)  # COCO dataset has 80 classes
    detectionNetwork.setCoordinateSize(4)
    detectionNetwork.setAnchors([])
    detectionNetwork.setAnchorMasks({})
    detectionNetwork.setIouThreshold(0.5)
    detectionNetwork.setBlobPath("yolov8n_coco_416x416_openvino_2022.1_6shave.blob")
    detectionNetwork.setNumInferenceThreads(2)
    detectionNetwork.input.setBlocking(False)
    detectionNetwork.input.setQueueSize(1)

    # Linking
    camRgb.preview.link(detectionNetwork.input)
    detectionNetwork.passthrough.link(xoutRgb.input)
    detectionNetwork.out.link(nnOut.input)

    return pipeline

# NN data, being the bounding box locations, are in <0..1> range - they need to be normalized with frame width/height
def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def displayFrame(name, frame, detections):
    for detection in detections:
        if detection.label == person_class_id:  # Only show person detections
            bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
            cv2.putText(frame, f"Person: {detection.confidence:.2f}", 
                        (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Show the frame
    cv2.imshow(name, frame)

def run_oak_detection():
    global latest_frame, latest_detections
    
    # Create output directory if specified
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to device and start pipeline
    device = dai.Device(setup_oak_pipeline())
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
    
    person_class_id = 0  # In COCO dataset, person class has ID 0
    
    print(f"People detection started - Web stream available at http://0.0.0.0:{args.port}")
    print(f"Confidence threshold: {args.threshold}")
    
    try:
        while True:
            inRgb = qRgb.get()
            inDet = qDet.get()

            if inRgb is not None:
                frame = inRgb.getCvFrame()
                with frame_lock:
                    latest_frame = frame.copy()

            if inDet is not None:
                with frame_lock:
                    latest_detections = inDet.detections

            # Check for people detections
            person_count = sum(1 for detection in latest_detections if detection.label == person_class_id)
            
            if person_count > 0:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"Detected {person_count} people at {timestamp}")
                
                # Save detected frame if output directory is specified
                if args.output:
                    with frame_lock:
                        if latest_frame is not None:
                            frame_with_detections = latest_frame.copy()
                            for detection in latest_detections:
                                if detection.label == person_class_id:
                                    bbox = frameNorm(frame_with_detections, 
                                                   (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                                    cv2.rectangle(frame_with_detections, (bbox[0], bbox[1]), (bbox[2], bbox[3]), 
                                                (0, 255, 0), 2)
                            
                            file_timestamp = time.strftime("%Y%m%d_%H%M%S")
                            filename = output_dir / f"person_detected_{file_timestamp}_{person_count}.jpg"
                            cv2.imwrite(str(filename), frame_with_detections)
                            print(f"Saved detection to {filename}")
            
            # Display the frame locally if requested
            if args.display and latest_frame is not None:
                with frame_lock:
                    displayFrame("People Detection", latest_frame, latest_detections)
                if cv2.waitKey(1) == ord('q'):
                    break
                    
            time.sleep(0.01)  # Small delay to reduce CPU usage

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        if args.display:
            cv2.destroyAllWindows()
        print("People detection stopped")

# Start the OAK-D detection in a separate thread
detection_thread = threading.Thread(target=run_oak_detection)
detection_thread.daemon = True  # Allow the program to exit even if the thread is running
detection_thread.start()

# Start the Flask web server
if __name__ == "__main__":
    # Start Flask server with threading enabled
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)

# Note: Before using this script, you need to download the YOLOv8nano model blob file.
# You can do this with the following steps:
# 1. Install depthai-sdk: pip install depthai-sdk
# 2. Download the model: python -m depthai_sdk.download_model.download_and_convert yolov8n --shaves 6
# 3. The blob will be saved in ~/.cache/depthai/yolov8n_openvino_2022.1_6shave.blob
# 4. Copy it to the same directory as this script