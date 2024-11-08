import depthai as dai
import cv2
import numpy as np
import json

with open('yolov8ntrained.json') as f:
    config = json.load(f)
input_size = tuple(map(int, config['nn_config']['input_size'].split('x')))
labels = config['mappings']['labels']
confidence_threshold = config['nn_config']['NN_specific_metadata']['confidence_threshold']

pipeline = dai.Pipeline()

cam_rgb = pipeline.create(dai.node.ColorCamera)
cam_rgb.setPreviewSize(*input_size)
cam_rgb.setInterleaved(False)

object_detector = pipeline.create(dai.node.NeuralNetwork)
object_detector.setBlobPath('./yolov8ntrained_openvino_2022.1_6shave.blob')
cam_rgb.preview.link(object_detector.input)

xout_rgb = pipeline.create(dai.node.XLinkOut)
xout_rgb.setStreamName("rgb")
cam_rgb.preview.link(xout_rgb.input)

xout_nn = pipeline.create(dai.node.XLinkOut)
xout_nn.setStreamName("nn")
object_detector.out.link(xout_nn.input)

with dai.Device(pipeline) as device:
    rgb_queue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    nn_queue = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
    
    while True:
        in_rgb = rgb_queue.get()
        in_nn = nn_queue.get()
        
        frame = in_rgb.getCvFrame()
        detections = np.array(in_nn.getFirstLayerFp16())
        
        if detections.size % 7 == 0:
            detections = detections.reshape((detections.size // 7, 7))
            
            for det in detections:
                conf = det[2]
                if conf > confidence_threshold:
                    x_min = int(det[3] * frame.shape[1])
                    y_min = int(det[4] * frame.shape[0])
                    x_max = int(det[5] * frame.shape[1])
                    y_max = int(det[6] * frame.shape[0])
                    class_id = int(det[1])
                    label = labels[class_id] if class_id < len(labels) else "Unknown"
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x_min, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        cv2.imshow("Frame", frame)
        
        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()
