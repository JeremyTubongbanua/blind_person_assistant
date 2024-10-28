import depthai as dai
import numpy as np
import blobconverter
import cv2

labelMap = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush"
]

pipeline = dai.Pipeline()

cameraRGB = pipeline.createColorCamera()
cameraRGB.setPreviewSize(256, 192)
cameraRGB.setInterleaved(False)

# Use YoloDetectionNetwork instead of MobileNetDetectionNetwork
detectionNN = pipeline.createYoloDetectionNetwork()
detectionNN.setBlobPath("models/yolov6n_thermal_people_256x192_openvino_2022.1_6shave.blob")
detectionNN.setConfidenceThreshold(0.5)

# Set the required properties for YOLO
detectionNN.setNumClasses(1)  # Assuming the model is trained to detect only 'person'
detectionNN.setCoordinateSize(4)
detectionNN.setAnchors([10,13, 16,30, 33,23, 30,61, 62,45, 59,119, 116,90, 156,198, 373,326])
detectionNN.setAnchorMasks({"side32": [6,7,8], "side16": [3,4,5], "side8": [0,1,2]})
detectionNN.setIouThreshold(0.5)
# detectionNN.setInputSize(256, 192)

xLinkOutCameraRGB = pipeline.createXLinkOut()
xLinkOutCameraRGB.setStreamName("cameraRGB")

xLinkOutDetectionNN = pipeline.createXLinkOut()
xLinkOutDetectionNN.setStreamName("detectionNN")

cameraRGB.preview.link(detectionNN.input)
cameraRGB.preview.link(xLinkOutCameraRGB.input)
detectionNN.out.link(xLinkOutDetectionNN.input)

device = dai.Device(pipeline)

queueCameraRGB = device.getOutputQueue(name="cameraRGB", maxSize=4)
queueDetectionNN = device.getOutputQueue(name="detectionNN", maxSize=4)

def normalizeFrame(frame, bbox):
    normVals = [frame.shape[1], frame.shape[0], frame.shape[1], frame.shape[0]]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

while True:
    cameraRGBFrame = queueCameraRGB.get()
    detectionNNData = queueDetectionNN.get()

    frame = cameraRGBFrame.getCvFrame()

    if detectionNNData is not None:
        detections = detectionNNData.detections
        print(f"Detected {len(detections)} objects")
        for detection in detections:
            bbox = normalizeFrame(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)

            # Since the model detects only 'person', we can set label to 'person'
            label = "person"
            cv2.putText(frame, f"{label} ({round(detection.confidence * 100, 2)}%)",
                        (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 0, 0), 2)

    cv2.imshow("preview", frame)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break

device.close()

exit(0)
