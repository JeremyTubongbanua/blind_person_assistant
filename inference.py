import cv2
import numpy as np
import depthai as dai
from pathlib import Path
from flask import Flask, Response, render_template_string
import threading
import time
from ultralytics import YOLO
import argparse

# Global variables
global_frame = None
frame_lock = threading.Lock()

class OAKDDepthDetector:
    def __init__(self, model_path="./best.pt", blob_path="./best.blob", use_spatial=False, conf_thresh=0.25):
        self.model_path = model_path
        self.blob_path = blob_path
        self.use_spatial = use_spatial
        self.conf_thresh = conf_thresh
        self.class_names = ['person', 'pole', 'garbage_can', 'door', 'exit_sign', 'general_sign', 'wet_floor_sign']
        self.running = False
        
        # Load the YOLO model for host-side inference if needed
        if not use_spatial:
            self.model = YOLO(model_path)
    
    def create_pipeline(self):
        """Create the DepthAI pipeline based on configuration"""
        pipeline = dai.Pipeline()
        
        # Create nodes
        camRgb = pipeline.create(dai.node.ColorCamera)
        monoLeft = pipeline.create(dai.node.MonoCamera)
        monoRight = pipeline.create(dai.node.MonoCamera)
        stereo = pipeline.create(dai.node.StereoDepth)
        
        # Configure RGB camera
        camRgb.setPreviewSize(416, 416)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        camRgb.setFps(30)
        
        # Configure mono cameras for depth
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        
        # Configure stereo depth
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(camRgb.getPreviewWidth(), camRgb.getPreviewHeight())
        
        # Create outputs
        xoutRgb = pipeline.create(dai.node.XLinkOut)
        xoutDepth = pipeline.create(dai.node.XLinkOut)
        xoutRgb.setStreamName("rgb")
        xoutDepth.setStreamName("depth")
        
        # Link mono cameras to stereo
        monoLeft.out.link(stereo.left)
        monoRight.out.link(stereo.right)
        
        if self.use_spatial and Path(self.blob_path).exists():
            # Spatial detection using on-device neural inference
            print("Setting up spatial detection with blob model")
            spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
            xoutNN = pipeline.create(dai.node.XLinkOut)
            xoutNN.setStreamName("detections")
            
            spatialDetectionNetwork.setBlobPath(str(self.blob_path))
            spatialDetectionNetwork.setConfidenceThreshold(self.conf_thresh)
            spatialDetectionNetwork.setNumClasses(len(self.class_names))
            spatialDetectionNetwork.setCoordinateSize(4)
            spatialDetectionNetwork.setAnchors([10,13, 16,30, 33,23, 30,61, 62,45, 59,119, 116,90, 156,198, 373,326])
            
            # Set anchor masks
            spatialDetectionNetwork.setAnchorMasks({
                "side26": [1, 2, 3], 
                "side13": [3, 4, 5], 
                "side52": [0, 1, 2]
            })
            
            spatialDetectionNetwork.setIouThreshold(0.5)
            spatialDetectionNetwork.setDepthLowerThreshold(100)
            spatialDetectionNetwork.setDepthUpperThreshold(5000)
            
            # Link inputs and outputs for spatial detection
            camRgb.preview.link(spatialDetectionNetwork.input)
            stereo.depth.link(spatialDetectionNetwork.inputDepth)
            spatialDetectionNetwork.passthrough.link(xoutRgb.input)
            spatialDetectionNetwork.out.link(xoutNN.input)
            stereo.depth.link(xoutDepth.input)
        else:
            # Basic setup for host-side inference
            print("Setting up basic depth estimation with host-side inference")
            camRgb.preview.link(xoutRgb.input)
            stereo.depth.link(xoutDepth.input)
        
        return pipeline
    
    def process_frame_with_host_inference(self, frame, depthFrame):
        """Process frame using host-side YOLO inference"""
        # Normalize depth for visualization
        depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
        depthFrameColor = cv2.equalizeHist(depthFrameColor)
        depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_JET)
        
        # Run YOLO inference
        results = self.model.predict(frame, conf=self.conf_thresh, verbose=False)[0]
        
        # Process detection results
        if results.boxes:
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # Get depth at center of bounding box
                centerX = (x1 + x2) // 2
                centerY = (y1 + y2) // 2
                
                if 0 <= centerX < depthFrame.shape[1] and 0 <= centerY < depthFrame.shape[0]:
                    depth_mm = depthFrame[centerY, centerX]
                    depth_m = depth_mm / 1000.0
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    if depth_m > 0:
                        label = f"{self.class_names[cls_id]}: {conf:.2f}, {depth_m:.2f}m"
                    else:
                        label = f"{self.class_names[cls_id]}: {conf:.2f}, depth N/A"
                        
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    cv2.circle(frame, (centerX, centerY), 4, (0, 0, 255), -1)
        
        # Combine RGB and depth frames
        # Resize depth frame to match RGB if needed
        if frame.shape[:2] != depthFrameColor.shape[:2]:
            depthFrameColor = cv2.resize(depthFrameColor, (frame.shape[1], frame.shape[0]))
            
        combined = np.hstack((frame, depthFrameColor))
        return combined
    
    def process_frame_with_spatial_detection(self, frame, depthFrame, detections):
        """Process frame with spatial detection results"""
        # Normalize depth for visualization
        depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
        depthFrameColor = cv2.equalizeHist(depthFrameColor)
        depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_JET)
        
        # Process detections
        for detection in detections:
            bbox = detection.boundingBox
            x1 = int(bbox.xmin * frame.shape[1])
            y1 = int(bbox.ymin * frame.shape[0])
            x2 = int(bbox.xmax * frame.shape[1])
            y2 = int(bbox.ymax * frame.shape[0])
            
            try:
                label = self.class_names[detection.label]
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
        
        # Combine RGB and depth frames
        if frame.shape[:2] != depthFrameColor.shape[:2]:
            depthFrameColor = cv2.resize(depthFrameColor, (frame.shape[1], frame.shape[0]))
            
        combined = np.hstack((frame, depthFrameColor))
        return combined
    
    def start(self):
        """Start the detection thread"""
        if not self.running:
            self.running = True
            self.detection_thread = threading.Thread(target=self.detection_loop)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            print("Detection thread started")
    
    def stop(self):
        """Stop the detection thread"""
        self.running = False
        if hasattr(self, 'detection_thread'):
            self.detection_thread.join(timeout=3)
            print("Detection thread stopped")
    
    def detection_loop(self):
        """Main detection loop running in a separate thread"""
        global global_frame
        
        # Create and check pipeline
        try:
            pipeline = self.create_pipeline()
            device_info_list = dai.Device.getAllAvailableDevices()
            if len(device_info_list) == 0:
                print("No devices found. Please connect your OAK-D device.")
                self.running = False
                return
            else:
                print(f"Found {len(device_info_list)} device(s).")
                for i, device_info in enumerate(device_info_list):
                    print(f"Device {i}: {device_info.getMxId()}")
        except Exception as e:
            print(f"Error creating pipeline: {e}")
            self.running = False
            return
        
        # Start device with pipeline
        try:
            with dai.Device(pipeline) as device:
                print(f"Connected to device: {device.getDeviceInfo().getMxId()}")
                
                # Create output queues
                qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
                qDepth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
                
                if self.use_spatial:
                    qDet = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
                
                print("Starting detection loop...")
                
                while self.running:
                    inRgb = qRgb.tryGet()
                    inDepth = qDepth.tryGet()
                    
                    if not inRgb or not inDepth:
                        time.sleep(0.01)  # Small sleep to prevent CPU spinning
                        continue
                    
                    frame = inRgb.getCvFrame()
                    depthFrame = inDepth.getFrame()
                    
                    if self.use_spatial:
                        # Process with spatial detection
                        inDet = qDet.tryGet()
                        detections = inDet.detections if inDet else []
                        output_frame = self.process_frame_with_spatial_detection(frame, depthFrame, detections)
                    else:
                        # Process with host-side inference
                        output_frame = self.process_frame_with_host_inference(frame, depthFrame)
                    
                    # Update the global frame with lock to prevent race conditions
                    with frame_lock:
                        global_frame = output_frame.copy()
                    
                    # Small delay to reduce CPU usage
                    time.sleep(0.01)
                
        except Exception as e:
            print(f"Error in detection loop: {e}")
            # If spatial detection fails, try to fall back to host inference
            if self.use_spatial:
                print("Spatial detection failed. Falling back to host inference.")
                self.use_spatial = False
                self.detection_loop()
        
        finally:
            self.running = False

def generate_frames():
    """Generator function for video streaming"""
    global global_frame
    
    while True:
        # Get the current frame with lock
        with frame_lock:
            if global_frame is None:
                # If no frame is available, generate a blank frame with message
                blank_frame = np.zeros((300, 600, 3), dtype=np.uint8)
                cv2.putText(blank_frame, "Waiting for camera...", (50, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                frame_to_yield = blank_frame
            else:
                frame_to_yield = global_frame.copy()
        
        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame_to_yield)
        if not ret:
            continue
            
        # Yield the frame in the format expected by Flask
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        # Small sleep to control frame rate
        time.sleep(0.03)  # ~30 FPS

def create_app(detector):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # HTML template for the main page
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OAK-D Object Detection Stream</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                text-align: center;
                background-color: #f0f0f0;
            }
            h1 {
                color: #333;
            }
            .video-container {
                margin: 20px auto;
                max-width: 90%;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            .video-stream {
                width: 100%;
                height: auto;
                border: 1px solid #ddd;
            }
            .footer {
                margin-top: 20px;
                color: #666;
                font-size: 0.8em;
            }
        </style>
    </head>
    <body>
        <h1>OAK-D Object Detection and Depth Stream</h1>
        <div class="video-container">
            <img src="{{ url_for('video_stream') }}" class="video-stream">
        </div>
        <div class="footer">
            <p>Classes: person, pole, garbage_can, door, exit_sign, general_sign, wet_floor_sign</p>
        </div>
    </body>
    </html>
    """
    
    @app.route('/')
    def index():
        """Route for the main page"""
        return render_template_string(html_template)
    
    @app.route('/video_stream')
    def video_stream():
        """Route for the video stream"""
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    
    return app

def main():
    parser = argparse.ArgumentParser(description="OAK-D Object Detection and Depth Stream Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host address to bind the server to')
    parser.add_argument('--port', type=int, default=8005, help='Port to run the server on')
    parser.add_argument('--spatial', action='store_true', help='Use spatial detection (requires blob model)')
    parser.add_argument('--model', type=str, default='./best.pt', help='Path to YOLO model')
    parser.add_argument('--blob', type=str, default='./best.blob', help='Path to blob model for spatial detection')
    parser.add_argument('--conf', type=float, default=0.25, help='Confidence threshold for detections')
    args = parser.parse_args()
    
    # Create the detector
    detector = OAKDDepthDetector(
        model_path=args.model,
        blob_path=args.blob,
        use_spatial=args.spatial,
        conf_thresh=args.conf
    )
    
    # Start the detector thread
    detector.start()
    
    # Create and run the Flask app
    app = create_app(detector)
    
    try:
        print(f"Starting web server on {args.host}:{args.port}")
        print("Access the stream at http://localhost:8005 (if running locally)")
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        detector.stop()

if __name__ == "__main__":
    main()