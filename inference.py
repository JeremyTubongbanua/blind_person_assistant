import cv2
import numpy as np
import depthai as dai
from pathlib import Path
from ultralytics import YOLO

def run_inference_with_depth(model_path, conf_thresh=0.25):
    model = YOLO(model_path)
    
    with open('dataset/classes.txt', 'r') as f:
        class_names = [line.strip() for line in f.readlines()]
    
    pipeline = dai.Pipeline()
    
    camRgb = pipeline.create(dai.node.ColorCamera)
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoRight = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)
    
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xoutDepth = pipeline.create(dai.node.XLinkOut)
    
    xoutRgb.setStreamName("rgb")
    xoutDepth.setStreamName("depth")
    
    camRgb.setPreviewSize(416, 416)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camRgb.setFps(30)
    
    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(camRgb.getPreviewWidth(), camRgb.getPreviewHeight())
    
    monoLeft.out.link(stereo.left)
    monoRight.out.link(stereo.right)
    camRgb.preview.link(xoutRgb.input)
    stereo.depth.link(xoutDepth.input)
    
    try:
        with dai.Device(pipeline) as device:
            print(f"Connected to device: {device.getDeviceInfo().getMxId()}")
            
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            qDepth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
            
            while True:
                inRgb = qRgb.get()
                inDepth = qDepth.get()
                
                frame = inRgb.getCvFrame()
                depthFrame = inDepth.getFrame()
                
                depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
                depthFrameColor = cv2.equalizeHist(depthFrameColor)
                depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_JET)
                
                results = model.predict(frame, conf=conf_thresh, verbose=False)[0]
                
                if results.boxes:
                    for box in results.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        
                        centerX = (x1 + x2) // 2
                        centerY = (y1 + y2) // 2
                        
                        if 0 <= centerX < depthFrame.shape[1] and 0 <= centerY < depthFrame.shape[0]:
                            depth_mm = depthFrame[centerY, centerX]
                            depth_m = depth_mm / 1000.0
                            
                            if depth_m > 0:
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                
                                label = f"{class_names[cls_id]}: {conf:.2f}, {depth_m:.2f}m"
                                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                
                                cv2.circle(frame, (centerX, centerY), 4, (0, 0, 255), -1)
                            else:
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                
                                label = f"{class_names[cls_id]}: {conf:.2f}, depth N/A"
                                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                combined = np.hstack((frame, depthFrameColor))
                cv2.imshow("RGB and Depth", combined)
                
                if cv2.waitKey(1) == ord('q'):
                    break
    
    except Exception as e:
        print(f"Error connecting to OAK-D Lite: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure no other application is using the camera")
        print("2. Try unplugging and replugging the device")
        print("3. On Linux, ensure you have proper udev rules")
        print("4. Try a different USB port, preferably USB 3.0")
        return
    
    finally:
        cv2.destroyAllWindows()

def run_inference_with_spatial_detection(model_path, conf_thresh=0.25):
    """
    Run inference with spatial detection. Falls back to basic depth inference if spatial detection fails.
    """
    print("Checking device availability...")
    # Verify a device is available before proceeding
    try:
        device_info_list = dai.Device.getAllAvailableDevices()
        if len(device_info_list) == 0:
            print("No devices found. Please connect your OAK-D device.")
            return
        else:
            print(f"Found {len(device_info_list)} device(s).")
            for i, device_info in enumerate(device_info_list):
                print(f"Device {i}: {device_info.getMxId()}")
    except Exception as e:
        print(f"Error checking devices: {e}")
        return
    with open('dataset/classes.txt', 'r') as f:
        class_names = [line.strip() for line in f.readlines()]
    
    blob_path = Path(model_path).with_suffix('.blob')
    if not blob_path.exists():
        print(f"Warning: Blob file not found at {blob_path}")
        print("For best performance, convert your model to blob format")
        print("Continuing with host-side inference...")
        run_inference_with_depth(model_path, conf_thresh)
        return
    
    pipeline = dai.Pipeline()
    
    camRgb = pipeline.create(dai.node.ColorCamera)
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoRight = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)
    
    spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xoutNN = pipeline.create(dai.node.XLinkOut)
    xoutDepth = pipeline.create(dai.node.XLinkOut)
    
    xoutRgb.setStreamName("rgb")
    xoutNN.setStreamName("detections")
    xoutDepth.setStreamName("depth")
    
    camRgb.setPreviewSize(416, 416)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camRgb.setFps(30)  # Added FPS setting
    
    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    monoLeft.setFps(30)  # Added FPS setting
    
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    monoRight.setFps(30)  # Added FPS setting
    
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(camRgb.getPreviewWidth(), camRgb.getPreviewHeight())
    
    spatialDetectionNetwork.setBlobPath(str(blob_path))
    spatialDetectionNetwork.setConfidenceThreshold(conf_thresh)
    spatialDetectionNetwork.setNumClasses(len(class_names))
    spatialDetectionNetwork.setCoordinateSize(4)
    spatialDetectionNetwork.setAnchors([10,13, 16,30, 33,23, 30,61, 62,45, 59,119, 116,90, 156,198, 373,326])
    
    # Fix anchor masks - Include the required "side3549" mask
    spatialDetectionNetwork.setAnchorMasks({
        "side26": [1, 2, 3], 
        "side13": [3, 4, 5], 
        "side52": [0, 1, 2],
        "side3549": [0, 1, 2, 3, 4, 5]  # Add the required mask for layer with width 3549
    })
    
    spatialDetectionNetwork.setIouThreshold(0.5)
    spatialDetectionNetwork.setDepthLowerThreshold(100)
    spatialDetectionNetwork.setDepthUpperThreshold(5000)
    
    # Link network inputs
    monoLeft.out.link(stereo.left)
    monoRight.out.link(stereo.right)
    camRgb.preview.link(spatialDetectionNetwork.input)
    stereo.depth.link(spatialDetectionNetwork.inputDepth)
    
    # Link network outputs
    spatialDetectionNetwork.passthrough.link(xoutRgb.input)
    spatialDetectionNetwork.out.link(xoutNN.input)
    stereo.depth.link(xoutDepth.input)
    
    try:
        print("Creating device with pipeline...")
        with dai.Device(pipeline) as device:
            print(f"Connected to device: {device.getDeviceInfo().getMxId()}")
            print(f"Device state: {device.getDeviceInfo().state}")
            
            # Create output queues
            print("Creating output queues...")
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
            qDepth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
            print("Output queues created successfully")
            
            frame_count = 0
            print("Starting detection loop...")
            start_time = cv2.getTickCount()
            
            # Add a timeout mechanism
            max_wait_seconds = 30
            timeout = False
            
            while True:
                # Check for timeout
                current_time = cv2.getTickCount()
                elapsed_seconds = (current_time - start_time) / cv2.getTickFrequency()
                
                if frame_count == 0 and elapsed_seconds > max_wait_seconds:
                    print(f"Timeout after {elapsed_seconds:.1f} seconds with no frames")
                    print("Check camera connections and permissions")
                    timeout = True
                    break
                
                # Print status every 5 seconds if no frames received
                if frame_count == 0 and elapsed_seconds % 5 < 0.1:
                    print(f"Waiting for frames... ({elapsed_seconds:.1f}s)")
                
                frame_count += 1
                
                # Non-blocking get prevents hanging on frame acquisition
                inRgb = qRgb.tryGet()
                inDet = qDet.tryGet()
                inDepth = qDepth.tryGet()
                
                # Print detailed frame queue status every 50 frames
                if frame_count % 50 == 1:
                    print(f"RGB frame: {'Available' if inRgb else 'None'}")
                    print(f"Depth frame: {'Available' if inDepth else 'None'}")
                    print(f"Detection frame: {'Available' if inDet else 'None'}")
                
                # Skip if any frame is missing
                if inRgb is None or inDepth is None:
                    continue
                
                frame = inRgb.getCvFrame()
                depthFrame = inDepth.getFrame()
                
                depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
                depthFrameColor = cv2.equalizeHist(depthFrameColor)
                depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_JET)
                
                # Print progress indication every 30 frames
                if frame_count % 30 == 0:
                    print(f"Processing frame {frame_count}")
                
                # Process detections if available
                if inDet is not None:
                    detections = inDet.detections
                    
                    for detection in detections:
                        bbox = detection.boundingBox
                        x1 = int(bbox.xmin * frame.shape[1])
                        y1 = int(bbox.ymin * frame.shape[0])
                        x2 = int(bbox.xmax * frame.shape[1])
                        y2 = int(bbox.ymax * frame.shape[0])
                        
                        try:
                            label = class_names[detection.label]
                        except IndexError:
                            label = f"Class {detection.label}"
                        
                        x = detection.spatialCoordinates.x / 1000.0
                        y = detection.spatialCoordinates.y / 1000.0 
                        z = detection.spatialCoordinates.z / 1000.0
                        
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        spatial_text = f"{label}: {detection.confidence:.2f}, {z:.2f}m"
                        cv2.putText(frame, spatial_text, (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        position_text = f"X: {x:.2f}m Y: {y:.2f}m"
                        cv2.putText(frame, position_text, (x1, y2 + 20), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Combine RGB and depth frames for display
                try:
                    # Resize to match if dimensions differ
                    if frame.shape[:2] != depthFrameColor.shape[:2]:
                        depthFrameColor = cv2.resize(depthFrameColor, (frame.shape[1], frame.shape[0]))
                    
                    combined = np.hstack((frame, depthFrameColor))
                    cv2.imshow("RGB and Depth with Spatial Detection", combined)
                except Exception as e:
                    print(f"Display error: {e}")
                    continue
                
                # Check for exit key
                key = cv2.waitKey(1)
                if key == ord('q'):
                    print("Exiting...")
                    break
    
    except Exception as e:
        print(f"Error with spatial detection: {e}")
        print("Error details:", repr(e))
        print(f"Error type: {type(e).__name__}")
        
        if isinstance(e, RuntimeError) and "Cannot create a direct link" in str(e):
            print("\nPossible pipeline configuration error")
            print("Trying alternative configuration...")
            try_alternative_pipeline(model_path, conf_thresh)
        else:
            print("Falling back to basic depth estimation...")
            run_inference_with_depth(model_path, conf_thresh)
    
    finally:
        cv2.destroyAllWindows()
        print("Program terminated.")
        
def try_alternative_pipeline(model_path, conf_thresh=0.25):
    """
    Try an alternative pipeline configuration that might resolve linking issues.
    """
    print("Using alternative pipeline configuration...")
    
    # Create blob path
    blob_path = Path(model_path).with_suffix('.blob')
    if not blob_path.exists():
        print(f"Blob file not found at {blob_path}, falling back to depth estimation")
        run_inference_with_depth(model_path, conf_thresh)
        return
        
    # Create pipeline with modified configuration
    pipeline = dai.Pipeline()
    
    # Create color camera
    camRgb = pipeline.create(dai.node.ColorCamera)
    camRgb.setPreviewSize(416, 416)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camRgb.setFps(30)
    
    # Create XLinkOut for RGB
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xoutRgb.setStreamName("rgb")
    camRgb.preview.link(xoutRgb.input)
    
    # Try to connect and run a simple RGB preview
    try:
        with dai.Device(pipeline) as device:
            print(f"Connected to device with alternative pipeline: {device.getDeviceInfo().getMxId()}")
            
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            
            print("Starting simplified loop...")
            for i in range(100):  # Just try to get 100 frames
                inRgb = qRgb.tryGet()
                if inRgb is not None:
                    frame = inRgb.getCvFrame()
                    cv2.imshow("RGB Preview", frame)
                    
                if cv2.waitKey(1) == ord('q'):
                    break
                    
            print("Alternative pipeline test completed")
            print("Falling back to basic depth estimation...")
            run_inference_with_depth(model_path, conf_thresh)
            
    except Exception as e:
        print(f"Error with alternative pipeline: {e}")
        print("Falling back to basic depth estimation...")
        run_inference_with_depth(model_path, conf_thresh)

if __name__ == "__main__":
    model_path = "yolov5_training/nano_speed/weights/best.pt"
    
    print("YOLOv5n with Depth Estimation on OAK-D Lite")
    print("1. Basic depth estimation with host inference")
    print("2. Advanced spatial detection (requires blob model)")
    choice = input("Select option (1/2) [default=1]: ").strip() or "1"
    
    if choice == "2":
        print("Starting spatial detection...")
        run_inference_with_spatial_detection(model_path)
    else:
        print("Starting basic depth estimation...")
        run_inference_with_depth(model_path)