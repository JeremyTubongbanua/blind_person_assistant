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
from flask import Flask, Response
import threading

# ---------------------------
# Flask App Setup
# ---------------------------
app = Flask(__name__)

# Global variable for the latest frame
latest_frame = None
lock = threading.Lock()

# ---------------------------
# DepthAI Pipeline + Inference
# ---------------------------

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--model", help="Provide model name or model path for inference", type=str)
parser.add_argument("-c", "--config", help="Provide config path for inference", type=str)
args = parser.parse_args()

# Parse config
configPath = Path(args.config)
if not configPath.exists():
    raise ValueError(f"Path {configPath} does not exist!")

with configPath.open() as f:
    config = json.load(f)
nnConfig = config.get("nn_config", {})

# Parse input shape
if "input_size" in nnConfig:
    W, H = tuple(map(int, nnConfig.get("input_size").split('x')))

# Extract metadata
metadata = nnConfig.get("NN_specific_metadata", {})
classes = metadata.get("classes", 80)  # Default to 80 if not found
coordinates = metadata.get("coordinates", 4)
anchors = metadata.get("anchors", [])
anchorMasks = metadata.get("anchor_masks", {})
iouThreshold = metadata.get("iou_threshold", 0.5)
confidenceThreshold = metadata.get("confidence_threshold", 0.5)

# Parse labels
nnMappings = config.get("mappings", {})
labels = nnMappings.get("labels", [])

# Load model blob
nnPath = Path(args.model)
if not nnPath.exists():
    print(f"No blob found at {nnPath}. Fetching from model zoo.")
    nnPath = blobconverter.from_zoo(args.model, shaves=13, zoo_type="depthai", use_cache=True)
nnPath = str(nnPath)

# Create pipeline
pipeline = dai.Pipeline()

# Define sources and outputs
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

# Camera properties
camRgb.setPreviewSize(W, H)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(40)

# ----------------------------------------------------------------------------
# Insert an ImageManip node to flip the camera image 180 degrees
# ----------------------------------------------------------------------------
imgManip = pipeline.create(dai.node.ImageManip)
# Instead of a rotation method, flip both horizontally and vertically.
imgManip.initialConfig.setHorizontalFlip(True)
imgManip.initialConfig.setVerticalFlip(True)
# Enforce the output resolution to match the model input.
imgManip.initialConfig.setResize(W, H)
# Set the maximum output frame size (BGR: 3 bytes per pixel).
imgManip.setMaxOutputFrameSize(W * H * 3)

# Mono camera properties for stereo depth
monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)

# Stereo depth properties
stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
stereo.setLeftRightCheck(True)
stereo.setSubpixel(True)

# Network settings
detectionNetwork.setBlobPath(nnPath)
detectionNetwork.setConfidenceThreshold(confidenceThreshold)
detectionNetwork.setNumClasses(classes)
detectionNetwork.setCoordinateSize(coordinates)
detectionNetwork.setAnchors(anchors)
detectionNetwork.setAnchorMasks(anchorMasks)
detectionNetwork.setIouThreshold(iouThreshold)
detectionNetwork.setNumInferenceThreads(2)
detectionNetwork.input.setBlocking(False)

# ----------------------------------------------------------------------------
# Pipeline Linking
# Instead of linking camRgb.preview directly to the network, we pass it through
# the ImageManip node so that the image is flipped before inference.
# ----------------------------------------------------------------------------
camRgb.preview.link(imgManip.inputImage)
imgManip.out.link(detectionNetwork.input)

detectionNetwork.passthrough.link(xoutRgb.input)
detectionNetwork.out.link(nnOut.input)

monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)
stereo.depth.link(xoutDepth.input)

def frameNorm(frame, bbox):
    """
    Converts normalized bbox to absolute pixel values.
    """
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def draw_detections(frame, detections, depthFrame):
    color = (255, 0, 0)
    for detection in detections:
        # Draw bounding box.
        bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)

        # Label.
        if detection.label < len(labels):
            label_text = labels[detection.label]
        else:
            label_text = f"Label {detection.label}"

        cv2.putText(
            frame,
            label_text,
            (bbox[0] + 10, bbox[1] + 20),
            cv2.FONT_HERSHEY_TRIPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        cv2.putText(
            frame,
            f"{int(detection.confidence * 100)}%",
            (bbox[0] + 10, bbox[1] + 40),
            cv2.FONT_HERSHEY_TRIPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        # Calculate and display distance (if depth frame is available).
        if depthFrame is not None:
            x1, y1, x2, y2 = bbox
            depth_slice = depthFrame[y1:y2, x1:x2]

            # Safety check in case the slice is empty.
            if depth_slice.size > 0:
                depth_val = np.median(depth_slice)
                if not np.isnan(depth_val):
                    distance = depth_val / 1000.0  # Convert from mm to meters.
                    cv2.putText(
                        frame,
                        f"Dist: {distance:.2f}m",
                        (bbox[0] + 10, bbox[1] + 60),
                        cv2.FONT_HERSHEY_TRIPLEX,
                        0.5,
                        (255, 255, 255),
                        1
                    )

def run_pipeline():
    """
    Runs the DepthAI pipeline in a loop and updates the global 'latest_frame'.
    """
    global latest_frame
    with dai.Device(pipeline) as device:
        qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
        qDepth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)

        startTime = time.monotonic()
        counter = 0
        depthFrame = None
        detections = []

        while True:
            inRgb = qRgb.get()
            inDet = qDet.get()
            inDepth = qDepth.tryGet()

            if inRgb is not None:
                frame = inRgb.getCvFrame()
                # Optional: show FPS.
                cv2.putText(
                    frame,
                    "NN fps: {:.2f}".format(counter / (time.monotonic() - startTime)),
                    (2, frame.shape[0] - 4),
                    cv2.FONT_HERSHEY_TRIPLEX,
                    0.4,
                    (255, 255, 255)
                )

            if inDet is not None:
                detections = inDet.detections
                counter += 1

            if inDepth is not None:
                depthFrame = inDepth.getFrame()

            if inRgb is not None:
                # Draw detections onto the frame.
                draw_detections(frame, detections, depthFrame)

                # Update the global latest_frame with a lock for thread safety.
                with lock:
                    latest_frame = frame.copy()

# ---------------------------
# Flask Video Stream Generator
# ---------------------------
def generate_frames():
    """
    Generator function that yields frames in a multipart HTTP response.
    """
    while True:
        with lock:
            if latest_frame is None:
                continue
            frame_copy = latest_frame.copy()

        ret, buffer = cv2.imencode('.jpg', frame_copy)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_stream')
def video_stream():
    """
    Flask route that serves the video stream.
    """
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ---------------------------
# Main
# ---------------------------
if __name__ == '__main__':
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    app.run(host='0.0.0.0', port=8005, debug=False, threaded=True)
