from pathlib import Path

import blobconverter
import cv2
import depthai
import numpy as np

pipeline = depthai.Pipeline()

cam_rgb = pipeline.createColorCamera()
cam_rgb.setPreviewSize(640, 360)
cam_rgb.setInterleaved(False)

manip = pipeline.createImageManip()
manip.initialConfig.setResize(300, 300)
manip.initialConfig.setFrameType(depthai.ImgFrame.Type.RGB888p)  # Set to planar format (CHW)

# Set up the MobileNet-SSD neural network
detection_nn = pipeline.createMobileNetDetectionNetwork()
detection_nn.setBlobPath(blobconverter.from_zoo(name='mobilenet-ssd', shaves=6))
detection_nn.setConfidenceThreshold(0.5)

# Set up output streams for both the RGB image and neural network results
xout_rgb = pipeline.createXLinkOut()
xout_rgb.setStreamName("rgb")

xout_nn = pipeline.createXLinkOut()
xout_nn.setStreamName("nn")

# Linking
cam_rgb.preview.link(xout_rgb.input)
cam_rgb.preview.link(manip.inputImage)  # Link camera preview to ImageManip for resizing
manip.out.link(detection_nn.input)  # Link resized and planar output to the NN
detection_nn.out.link(xout_nn.input)

with depthai.Device(pipeline) as device:
    q_rgb = device.getOutputQueue("rgb")
    q_nn = device.getOutputQueue("nn")
    frame = None
    detections = []

    def frameNorm(frame, bbox):
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

    while True:
        in_rgb = q_rgb.tryGet()
        in_nn = q_nn.tryGet()

        if in_rgb is not None:
            frame = in_rgb.getCvFrame()

        if in_nn is not None:
            detections = in_nn.detections

        if frame is not None:
            # Only track the person with the highest confidence level
            highest_confidence_person = None
            for detection in detections:
                if detection.label == 15:  # Label 15 corresponds to 'person'
                    if highest_confidence_person is None or detection.confidence > highest_confidence_person.confidence:
                        highest_confidence_person = detection

            if highest_confidence_person is not None:
                bbox = frameNorm(frame, (highest_confidence_person.xmin, highest_confidence_person.ymin, 
                                         highest_confidence_person.xmax, highest_confidence_person.ymax))
                # Calculate the center x and y of the bounding box
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                print(f"Center X: {center_x}, Center Y: {center_y}")  # Print the center x and y coordinates
                
                # Draw the rectangle on the frame
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)

            cv2.imshow("preview", frame)

        if cv2.waitKey(1) == ord('q'):
            break
