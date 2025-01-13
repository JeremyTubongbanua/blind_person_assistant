from pathlib import Path
import blobconverter
import cv2
import depthai
import numpy as np
from flask import Flask, Response

app = Flask(__name__)

pipeline = depthai.Pipeline()
cam_rgb = pipeline.createColorCamera()
cam_rgb.setPreviewSize(640, 360)
cam_rgb.setInterleaved(False)

manip = pipeline.createImageManip()
manip.initialConfig.setResize(300, 300)
manip.initialConfig.setFrameType(depthai.ImgFrame.Type.RGB888p)

detection_nn = pipeline.createMobileNetDetectionNetwork()
detection_nn.setBlobPath(blobconverter.from_zoo(name='mobilenet-ssd', shaves=6))
detection_nn.setConfidenceThreshold(0.5)

xout_rgb = pipeline.createXLinkOut()
xout_rgb.setStreamName("rgb")

xout_nn = pipeline.createXLinkOut()
xout_nn.setStreamName("nn")

cam_rgb.preview.link(xout_rgb.input)
cam_rgb.preview.link(manip.inputImage)
manip.out.link(detection_nn.input)
detection_nn.out.link(xout_nn.input)

device = depthai.Device(pipeline)
q_rgb = device.getOutputQueue("rgb")
q_nn = device.getOutputQueue("nn")
frame = None
detections = []

def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def generate_frames():
    global frame, detections
    while True:
        in_rgb = q_rgb.tryGet()
        in_nn = q_nn.tryGet()

        if in_rgb is not None:
            frame = in_rgb.getCvFrame()

        if in_nn is not None:
            detections = in_nn.detections

        if frame is not None:
            highest_confidence_person = None
            for detection in detections:
                if detection.label == 15:  # Label 15 for 'person'
                    if highest_confidence_person is None or detection.confidence > highest_confidence_person.confidence:
                        highest_confidence_person = detection

            if highest_confidence_person is not None:
                bbox = frameNorm(frame, (highest_confidence_person.xmin, highest_confidence_person.ymin, 
                                         highest_confidence_person.xmax, highest_confidence_person.ymax))
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                print(f"Center X: {center_x}, Center Y: {center_y}")
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
