@app.route('/detections')
def get_detections():
    global latest_frame, latest_detections, processing_detections, device
    
    if latest_frame is None:
        return jsonify({"error": "No frame available"})
    
    # Check if device is initialized
    if device is None:
        return jsonify({"error": "Camera device not initialized"})
    
    try:
        # Set flag to process detections in the main thread
        processing_detections = True
        
        # Wait for detections to be processed (with timeout)
        timeout = time.time() + 2.0  # 2 second timeout
        while processing_detections and time.time() < timeout:
            time.sleep(0.05)
        
        if processing_detections:
            # If still processing after timeout, assume issue with detection
            processing_detections = False
            return jsonify({"error": "Detection timeout, no results received from neural network"})
        
        # Get detections with lock
        detections = []
        with detection_lock:
            for detection in latest_detections:
                label_id = detection.label
                if label_id < len(labels):
                    label_name = labels[label_id]
                else:
                    label_name = f"Class {label_id}"
                
                confidence = detection.confidence
                
                if confidence >= confidence_threshold:
                    bbox = frameNorm(latest_frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                    detections.append({
                        "label": label_name,
                        "confidence": float(confidence),
                        "bbox": {
                            "x1": int(bbox[0]),
                            "y1": int(bbox[1]),
                            "x2": int(bbox[2]),
                            "y2": int(bbox[3])
                        }
                    })
        
        # Count occurrences of each class
        class_counts = {}
        for detection in detections:
            label = detection["label"]
            if label in class_counts:
                class_counts[label] += 1
            else:
                class_counts[label] = 1
        
        return jsonify({
            "timestamp": time.time(),
            "detected_classes": class_counts,
            "detections": detections
        })
    except Exception as e:
        return jsonify({
            "error": f"Error processing detections: {str(e)}"
        })import cv2
import depthai as dai
import numpy as np
import time
import json
from flask import Flask, Response, jsonify
import threading

with open('yolov8ntrained.json', 'r') as f:
    model_config = json.load(f)

labels = model_config['mappings']['labels']
confidence_threshold = 0.8  # Setting confidence threshold to 0.8

app = Flask(__name__)

def create_pipeline():
    pipeline = dai.Pipeline()
    
    camRgb = pipeline.create(dai.node.ColorCamera)
    detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    nnOut = pipeline.create(dai.node.XLinkOut)
    
    xoutRgb.setStreamName("rgb")
    nnOut.setStreamName("nn")
    
    camRgb.setPreviewSize(640, 640)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camRgb.setFps(30)
    
    detectionNetwork.setBlobPath("yolov8ntrained_openvino_2022.1_6shave.blob")
    detectionNetwork.setConfidenceThreshold(confidence_threshold)
    detectionNetwork.setNumClasses(model_config['nn_config']['NN_specific_metadata']['classes'])
    detectionNetwork.setCoordinateSize(model_config['nn_config']['NN_specific_metadata']['coordinates'])
    detectionNetwork.setAnchors([])
    detectionNetwork.setAnchorMasks({})
    detectionNetwork.setIouThreshold(model_config['nn_config']['NN_specific_metadata']['iou_threshold'])
    detectionNetwork.setNumInferenceThreads(2)
    detectionNetwork.input.setBlocking(False)
    
    camRgb.preview.link(detectionNetwork.input)
    detectionNetwork.passthrough.link(xoutRgb.input)
    detectionNetwork.out.link(nnOut.input)
    
    return pipeline

latest_frame = None
latest_detections = []
device = None
frame_lock = threading.Lock()
detection_lock = threading.Lock()
processing_detections = False

def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

# Placeholder for frame when device is disconnected
def create_placeholder_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Connecting to camera..."
    textsize = cv2.getTextSize(text, font, 1, 2)[0]
    text_x = (frame.shape[1] - textsize[0]) // 2
    text_y = (frame.shape[0] + textsize[1]) // 2
    cv2.putText(frame, text, (text_x, text_y), font, 1, (255, 255, 255), 2)
    return frame

def run_pipeline():
    global latest_frame, latest_detections, device, processing_detections
    
    retry_delay = 2  # Initial retry delay in seconds
    max_retry_delay = 30  # Maximum retry delay
    
    while True:
        try:
            # Check if there's already another process using the device
            try:
                device_info_list = dai.DeviceBootloader.getAllAvailableDevices()
                if len(device_info_list) == 0:
                    print("No devices found. Waiting...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                    continue
                
                # Try to find available devices
                available_devices = []
                for device_info in device_info_list:
                    try:
                        # Try to open the device briefly to check if it's available
                        temp_device = dai.Device(dai.DeviceInfo(device_info.getMxId()))
                        temp_device.close()
                        available_devices.append(device_info)
                    except Exception:
                        # This device is likely in use by another process
                        pass
                
                if not available_devices:
                    print("All devices are in use. Waiting...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                    continue
                
            except Exception as e:
                print(f"Error checking device availability: {e}")
            
            pipeline = create_pipeline()
            device = dai.Device(pipeline)
            
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)
            
            print("Starting video stream...")
            retry_delay = 2  # Reset retry delay on successful connection
            
            while True:
                try:
                    inRgb = qRgb.get()
                    frame = inRgb.getCvFrame()
                    
                    with frame_lock:
                        latest_frame = frame.copy()
                    
                    if processing_detections:
                        inDet = qDet.tryGet()
                        if inDet is not None:
                            with detection_lock:
                                latest_detections = inDet.detections
                                processing_detections = False
                    
                    time.sleep(0.01)
                except dai.XLinkError as e:
                    print(f"XLink error during frame processing: {e}")
                    break
                except Exception as e:
                    print(f"Error during frame processing: {e}")
                    time.sleep(1)
        
        except dai.XLinkError as e:
            print(f"XLink error during device initialization: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, max_retry_delay)
        except Exception as e:
            print(f"Error during device initialization: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, max_retry_delay)
        
        print("Attempting to reconnect to device...")
        
        # Clean up before reconnect attempt
        try:
            if device is not None:
                device.close()
                device = None
        except:
            pass

def generate_frames():
    global latest_frame
    while True:
        try:
            current_frame = None
            with frame_lock:
                if latest_frame is not None:
                    current_frame = latest_frame.copy()
                else:
                    current_frame = create_placeholder_frame()
            
            ret, buffer = cv2.imencode('.jpg', current_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            placeholder = create_placeholder_frame()
            ret, buffer = cv2.imencode('.jpg', placeholder)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.033)  # ~30 FPS

# Set initial placeholder frame
with frame_lock:
    latest_frame = create_placeholder_frame()

# Start pipeline thread
pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
pipeline_thread.start()

@app.route('/camera_status')
def camera_status():
    global device
    
    if device is None:
        return jsonify({"connected": False, "message": "Device not initialized"})
    
    try:
        # Try to get device info to check if it's still responsive
        device_info = device.getDeviceInfo()
        return jsonify({"connected": True, "device_id": device_info.getMxId()})
    except Exception as e:
        return jsonify({"connected": False, "message": str(e)})

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Oak-D Lite Camera Stream</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .video-container { position: relative; display: inline-block; }
            .stream { max-width: 100%; border: 1px solid #ddd; }
            #detectionCanvas { position: absolute; top: 0; left: 0; }
            .controls { margin: 15px 0; }
            button { padding: 5px 10px; margin-right: 10px; }
            .results-container { display: flex; }
            .canvas-container { margin-right: 20px; }
            pre { background: #f5f5f5; padding: 10px; max-height: 300px; overflow: auto; flex: 1; }
            .status { padding: 10px; margin-bottom: 15px; border-radius: 4px; }
            .status.connected { background-color: #d4edda; color: #155724; }
            .status.disconnected { background-color: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <h1>Oak-D Lite Camera Stream</h1>
        <div id="statusBar" class="status disconnected">Camera Status: Checking connection...</div>
        <div class="video-container">
            <img id="videoStream" class="stream" src="/video_stream" alt="Video Stream" onload="updateCanvasSize()">
            <canvas id="detectionCanvas"></canvas>
        </div>
        <div class="controls">
            <button id="detectBtn">Run Detection</button>
            <button id="clearBtn">Clear Detections</button>
        </div>
        <div class="results-container">
            <pre id="detectionResults"></pre>
        </div>
        
        <script>
            const canvas = document.getElementById('detectionCanvas');
            const ctx = canvas.getContext('2d');
            const videoStream = document.getElementById('videoStream');
            const statusBar = document.getElementById('statusBar');
            
            function updateCanvasSize() {
                canvas.width = videoStream.clientWidth;
                canvas.height = videoStream.clientHeight;
            }
            
            window.addEventListener('resize', updateCanvasSize);
            
            function drawBoundingBox(bbox, label, confidence) {
                const x = bbox.x1;
                const y = bbox.y1;
                const width = bbox.x2 - bbox.x1;
                const height = bbox.y2 - bbox.y1;
                
                // Scale coordinates to match the canvas size
                const scaleX = canvas.width / videoStream.naturalWidth;
                const scaleY = canvas.height / videoStream.naturalHeight;
                
                const scaledX = x * scaleX;
                const scaledY = y * scaleY;
                const scaledWidth = width * scaleX;
                const scaledHeight = height * scaleY;
                
                // Draw rectangle
                ctx.strokeStyle = '#00FF00';
                ctx.lineWidth = 2;
                ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
                
                // Draw background for text
                ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                ctx.fillRect(scaledX, scaledY - 20, scaledWidth, 20);
                
                // Draw text
                ctx.fillStyle = '#FFFFFF';
                ctx.font = '12px Arial';
                ctx.fillText(`${label} (${(confidence * 100).toFixed(0)}%)`, scaledX + 5, scaledY - 5);
            }
            
            function checkCameraStatus() {
                fetch('/camera_status')
                    .then(response => response.json())
                    .then(data => {
                        if (data.connected) {
                            statusBar.className = 'status connected';
                            statusBar.textContent = 'Camera Status: Connected';
                            document.getElementById('detectBtn').disabled = false;
                        } else {
                            statusBar.className = 'status disconnected';
                            statusBar.textContent = 'Camera Status: Disconnected - ' + data.message;
                            document.getElementById('detectBtn').disabled = true;
                        }
                    })
                    .catch(() => {
                        statusBar.className = 'status disconnected';
                        statusBar.textContent = 'Camera Status: Error checking connection';
                    });
            }
            
            // Check camera status every 5 seconds
            setInterval(checkCameraStatus, 5000);
            checkCameraStatus(); // Initial check
            
            document.getElementById('detectBtn').addEventListener('click', function() {
                fetch('/detections')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('detectionResults').textContent = JSON.stringify(data, null, 2);
                        
                        // Clear previous drawings
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        
                        // Draw new bounding boxes
                        if (data.detections && data.detections.length > 0) {
                            data.detections.forEach(detection => {
                                drawBoundingBox(detection.bbox, detection.label, detection.confidence);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching detections:', error);
                        document.getElementById('detectionResults').textContent = 'Error fetching detections';
                    });
            });
            
            document.getElementById('clearBtn').addEventListener('click', function() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                document.getElementById('detectionResults').textContent = '';
            });
            
            // Initialize canvas size after the video loads
            updateCanvasSize();
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8005, debug=False, threaded=True)