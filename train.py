"""
YOLOv5n (Nano) Transfer Learning Tutorial for OAK-D Lite
"""

import os
import yaml
from pathlib import Path

def setup_dataset_config():
    dataset_path = Path("dataset")
    
    data = {
        'train': str(Path.cwd() / dataset_path / 'images' / 'train'),
        'val': str(Path.cwd() / dataset_path / 'images' / 'test'),
        'nc': 0,
        'names': []
    }
    
    with open(dataset_path / 'classes.txt', 'r') as f:
        class_names = [line.strip() for line in f.readlines()]
    
    data['nc'] = len(class_names)
    data['names'] = class_names
    
    config_path = dataset_path / 'dataset.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    
    print(f"Dataset configuration created at {config_path}")
    return config_path

def setup_model_config():
    with open('dataset/classes.txt', 'r') as f:
        num_classes = len(f.readlines())
    
    print(f"Dataset has {num_classes} classes")
    return num_classes
    
    # For YOLOv5n we just need to know the number of classes
    return num_classes

def train_model(dataset_config, num_classes, pretrained_weights=None):
    from ultralytics import YOLO
    
    if pretrained_weights:
        model = YOLO(pretrained_weights)
        print(f"Loaded custom pretrained weights from {pretrained_weights}")
    else:
        model = YOLO('yolov5nu.pt')
        print("Using pretrained YOLOv5n weights - optimized for speed on edge devices")

    training_args = {
        'data': dataset_config,
        'epochs': 100,
        'batch': 16,
        'imgsz': 416,
        'device': 'cpu',
        'workers': 4,
        'patience': 30,
        'save_period': 10,
        'project': 'yolov5_training',
        'name': 'nano_speed',
        'exist_ok': True,
        'pretrained': True,
        'optimizer': 'Adam',
        'lr0': 0.001,
        'lrf': 0.01,
        'momentum': 0.937,
        'weight_decay': 0.0005,
        'warmup_epochs': 3,
        'warmup_momentum': 0.8,
        'warmup_bias_lr': 0.1,
        'max_det': 300,
        'iou': 0.65,
        'rect': False,
        'cache': False,
        'verbose': True
    }
    
    results = model.train(**training_args)
    print(f"Training completed. Results saved to {training_args['project']}/{training_args['name']}")
    
    return results
    
    # Start training
    results = model.train(**training_args)
    print(f"Training completed. Results saved to {training_args['project']}/{training_args['name']}")
    
    return results

def evaluate_model(model_path):
    from ultralytics import YOLO
    
    model = YOLO(model_path)
    
    results = model.val(data='dataset/dataset.yaml', batch=16, imgsz=416)
    
    print("Evaluation results:")
    print(f"mAP@0.5: {results.box.map50:.4f}")
    print(f"mAP@0.5:0.95: {results.box.map:.4f}")
    
    return results

def export_for_oakd(model_path):
    from ultralytics import YOLO
    import os
    
    model = YOLO(model_path)
    
    onnx_path = model_path.with_suffix('.onnx')
    success = model.export(format='onnx', imgsz=416)
    
    if success:
        print(f"Model exported to ONNX format at {onnx_path}")
        
        try:
            import subprocess
            output_dir = os.path.dirname(onnx_path) + '/openvino_model'
            os.makedirs(output_dir, exist_ok=True)
            
            cmd = [
                'mo',
                '--input_model', str(onnx_path),
                '--output_dir', output_dir,
                '--data_type', 'FP16'
            ]
            
            subprocess.run(cmd, check=True)
            print(f"Model converted to OpenVINO IR format at {output_dir}")
            
            return output_dir + '/model.xml'
        except Exception as e:
            print(f"Error converting to OpenVINO: {e}")
            print("If OpenVINO toolkit is not installed, please install it:")
            print("pip install openvino-dev")
            return None
    else:
        print("Failed to export model to ONNX format")
        return None

def deploy_to_oakd(model_path, confidence=0.5, image_size=416):
    try:
        import depthai as dai
        import cv2
        import time
        import numpy as np
        
        with open('dataset/classes.txt', 'r') as f:
            class_names = [line.strip() for line in f.readlines()]
        
        pipeline = dai.Pipeline()
        
        camRgb = pipeline.create(dai.node.ColorCamera)
        detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
        xoutRgb = pipeline.create(dai.node.XLinkOut)
        nnOut = pipeline.create(dai.node.XLinkOut)
        
        xoutRgb.setStreamName("rgb")
        nnOut.setStreamName("nn")
        
        camRgb.setPreviewSize(image_size, image_size)
        camRgb.setInterleaved(False)
        camRgb.setFps(30)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
        
        detectionNetwork.setConfidenceThreshold(confidence)
        detectionNetwork.setNumClasses(len(class_names))
        detectionNetwork.setCoordinateSize(4)
        
        detectionNetwork.setAnchors([10,13, 16,30, 33,23, 30,61, 62,45, 59,119, 116,90, 156,198, 373,326])
        detectionNetwork.setAnchorMasks({"side26": [1, 2, 3], "side13": [3, 4, 5], "side52": [0, 1, 2]})
        detectionNetwork.setIouThreshold(0.5)
        
        detectionNetwork.setBlobPath(model_path)
        detectionNetwork.setNumInferenceThreads(2)
        detectionNetwork.input.setBlocking(False)
        
        camRgb.preview.link(detectionNetwork.input)
        detectionNetwork.passthrough.link(xoutRgb.input)
        detectionNetwork.out.link(nnOut.input)
        
        with dai.Device(pipeline) as device:
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
            
            frame = None
            detections = []
            startTime = time.monotonic()
            counter = 0
            fps = 0
            color = (255, 255, 255)
            
            print("Starting detection on OAK-D Lite. Press 'q' to quit.")
            
            while True:
                inRgb = qRgb.get()
                inDet = qDet.get()
                
                if inRgb is not None:
                    frame = inRgb.getCvFrame()
                    cv2.putText(frame, "FPS: {:.2f}".format(fps), (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                if inDet is not None:
                    detections = inDet.detections
                    counter += 1
                    
                    current_time = time.monotonic()
                    if (current_time - startTime) > 1:
                        fps = counter / (current_time - startTime)
                        counter = 0
                        startTime = current_time
                
                if frame is not None:
                    for detection in detections:
                        bbox = detection.boundingBox
                        x1 = int(bbox.xmin * frame.shape[1])
                        y1 = int(bbox.ymin * frame.shape[0])
                        x2 = int(bbox.xmax * frame.shape[1])
                        y2 = int(bbox.ymax * frame.shape[0])
                        
                        try:
                            label = class_names[detection.label]
                        except:
                            label = f"Class {detection.label}"
                        
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label}: {int(detection.confidence * 100)}%", 
                                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    cv2.imshow("YOLOv5n on OAK-D Lite", frame)
                
                if cv2.waitKey(1) == ord('q'):
                    break
            
            cv2.destroyAllWindows()
    
    except ImportError:
        print("Could not import depthai. Make sure it's installed:")
        print("pip install depthai opencv-python")
    except Exception as e:
        print(f"Error deploying to OAK-D Lite: {e}")

if __name__ == "__main__":
    print("Starting YOLOv5n (Nano) transfer learning setup for maximum speed...")
    
    dataset_config = setup_dataset_config()
    
    num_classes = setup_model_config()
    
    results = train_model(dataset_config, num_classes)
    
    best_model_path = Path('yolov5_training/nano_speed/weights/best.pt')
    
    eval_results = evaluate_model(best_model_path)
    
    openvino_model = export_for_oakd(best_model_path)
    
    if openvino_model:
        print(f"\nTraining, evaluation, and export completed.")
        print(f"Best model saved at {best_model_path}")
        print(f"OpenVINO model for OAK-D Lite saved at {openvino_model}")
        
        deploy = input("Do you want to deploy and test on OAK-D Lite? (y/n): ")
        if deploy.lower() == 'y':
            deploy_to_oakd(openvino_model)
    else:
        print(f"\nTraining and evaluation completed. Best model saved at {best_model_path}")
        print("To use the trained model for inference:")
        print(f"from ultralytics import YOLO")
        print(f"model = YOLO('{best_model_path}')")
        print(f"model.predict('path/to/image.jpg')")