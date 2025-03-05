#!/usr/bin/env python3

import cv2
import depthai as dai
import numpy as np
import time
import blobconverter

# Download the model from DepthAI Model Zoo
blob_path = blobconverter.from_zoo(
    name="mobilenet-ssd", 
    shaves=6,  # Adjust based on your OAK-D Lite (6 is common for OAK-D Lite)
    zoo_type="depthai"
)

# Create pipeline
pipeline = dai.Pipeline()

# Define sources and outputs
camRgb = pipeline.create(dai.node.ColorCamera)
detectionNetwork = pipeline.create(dai.node.MobileNetDetectionNetwork)
xoutRgb = pipeline.create(dai.node.XLinkOut)
nnOut = pipeline.create(dai.node.XLinkOut)

xoutRgb.setStreamName("rgb")
nnOut.setStreamName("nn")

# Properties
camRgb.setPreviewSize(300, 300)  # MobileNet-SSD input size
camRgb.setInterleaved(False)
camRgb.setFps(30)

# Setup MobileNet-SSD network
detectionNetwork.setConfidenceThreshold(0.5)
detectionNetwork.setBlobPath(blob_path)

# COCO class labels
labelMap = ["background", "person", "bicycle", "car", "motorcycle", "airplane", "bus",
            "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter",
            "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
            "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis",
            "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
            "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
            "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
            "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv",
            "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster",
            "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
            "toothbrush"]

# Linking
camRgb.preview.link(detectionNetwork.input)
detectionNetwork.out.link(nnOut.input)
camRgb.preview.link(xoutRgb.input)

# Connect to device and start pipeline
with dai.Device(pipeline) as device:
    # Output queues
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

    frame = None
    detections = []
    startTime = time.monotonic()
    counter = 0
    color2 = (255, 255, 255)

    # nn data, being the bounding box locations, are in in normalized form
    # Frame normalization [0-1] where (0,0) is the top left corner and (1,1) is the bottom right
    def frameNorm(frame, bbox):
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

    while True:
        # Get RGB frame
        inRgb = qRgb.get()
        if inRgb is not None:
            frame = inRgb.getCvFrame()
            cv2.putText(frame, "NN fps: {:.2f}".format(counter / (time.monotonic() - startTime)),
                        (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color2)

        # Get detection network results
        inDet = qDet.tryGet()
        if inDet is not None:
            detections = inDet.detections
            counter += 1

        # If the frame is available, draw bounding boxes on it and show the frame
        if frame is not None:
            for detection in detections:
                # Denormalize bounding box
                bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                
                # Get label id and confidence
                label = labelMap[detection.label]
                confidence = detection.confidence
                
                # Draw rectangle
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)
                
                # Add label and confidence
                cv2.putText(frame, f"{label}: {int(confidence*100)}%", 
                           (bbox[0] + 10, bbox[1] + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 255, 0))

            # Show the frame
            cv2.imshow("MobileNet-SSD on OAK-D Lite", frame)

        if cv2.waitKey(1) == ord('q'):
            break