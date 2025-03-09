import cv2
import depthai as dai
import numpy as np
import time
import json
from flask import Flask, Response, jsonify
import threading

with open('yolov8ntrained.json', 'r') as f:
    model_config = json.load(f)

labels = model_config['mappings']['labels']
confidence_threshold = 0.8

app = Flask(__name__)

def create_pipeline():
    pipeline = dai.Pipeline()
    
    camRgb = pipeline.create(dai.node.ColorCamera)
    detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    nnOut = pipeline.create(dai.node.XLinkOut)
    xinFrame = pipeline.create(dai.node.XLinkIn)
    
    xoutRgb.setStreamName("rgb")
    nnOut.setStreamName("nn")
    xinFrame.setStreamName("frame_in")
    
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
    
    camRgb.preview.link(xoutRgb.input)
    
    xinFrame.out.link(detectionNetwork.input)
    detectionNetwork.out.link(nnOut.input)
    
    return pipeline

latest_frame = None
device = None
frame_lock = threading.Lock()
running_inference = False

def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def create_placeholder_frame(message="Connecting to camera..."):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = message
    textsize = cv2.getTextSize(text, font, 1, 2)[0]
    text_x = (frame.shape[1] - textsize[0]) // 2
    text_y = (frame.shape[0] + textsize[1]) // 2
    cv2.putText(frame, text, (text_x, text_y), font, 1, (255, 255, 255), 2)
    
    if "in use" in message.lower():
        instruction = "Please close other applications using the camera"
        inst_size = cv2.getTextSize(instruction, font, 0.5, 1)[0]
        inst_x = (frame.shape[1] - inst_size[0]) // 2
        inst_y = text_y + 40
        cv2.putText(frame, instruction, (inst_x, inst_y), font, 0.5, (255, 255, 255), 1)
    
    return frame

def run_pipeline():
    global latest_frame, device
    consecutive_errors = 0
    max_consecutive_errors = 5
    device_in_use = False
    
    while True:
        try:
            if device_in_use:
                with frame_lock:
                    latest_frame = create_placeholder_frame("Camera in use by another application")
                time.sleep(2)
                device_in_use = False
                consecutive_errors = 0
                
            pipeline = create_pipeline()
            device = dai.Device(pipeline)
            
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            
            print("Starting video stream...")
            consecutive_errors = 0
            
            while True:
                try:
                    inRgb = qRgb.get()
                    frame = inRgb.getCvFrame()
                    
                    frame = cv2.flip(frame, 0)
                    
                    with frame_lock:
                        latest_frame = frame.copy()
                    
                    time.sleep(0.01)
                except dai.XLinkError as e:
                    print(f"XLink error during frame processing: {e}")
                    if "X_LINK_ERROR" in str(e):
                        device_in_use = True
                    break
                except Exception as e:
                    consecutive_errors += 1
                    print(f"Error during frame processing: {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        break
                    time.sleep(1)
        
        except dai.XLinkError as e:
            print(f"XLink error during device initialization: {e}")
            if "X_LINK_DEVICE_ALREADY_IN_USE" in str(e) or "X_LINK_ERROR" in str(e):
                device_in_use = True
                print("Device appears to be in use by another application")
                with frame_lock:
                    latest_frame = create_placeholder_frame("Camera in use by another application")
            time.sleep(2)
        except Exception as e:
            print(f"Error during device initialization: {e}")
            consecutive_errors += 1
            time.sleep(2)
        
        print("Attempting to reconnect to device...")
        
        try:
            if device is not None:
                device.close()
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
        
        time.sleep(0.033)

with frame_lock:
    latest_frame = create_placeholder_frame()

pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
pipeline_thread.start()

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detections')
def get_detections():
    global latest_frame, device, running_inference
    
    if latest_frame is None:
        return jsonify({"error": "No frame available"})
    
    if device is None:
        return jsonify({"error": "Camera device not initialized", "status": "disconnected"})
    
    if running_inference:
        return jsonify({"error": "Detection already in progress", "status": "busy"})
    
    running_inference = True
    
    placeholder_check = np.sum(latest_frame[:, :, 0]) + np.sum(latest_frame[:, :, 1]) + np.sum(latest_frame[:, :, 2])
    if placeholder_check < 10000:
        running_inference = False
        return jsonify({
            "error": "Camera not available or in use by another application", 
            "status": "unavailable",
            "detections": []
        })
    
    try:
        frame_copy = None
        with frame_lock:
            if latest_frame is not None:
                frame_copy = latest_frame.copy()
            else:
                running_inference = False
                return jsonify({"error": "No frame available for detection"})
        
        # Set up dedicated inference queues
        nn_in = device.getInputQueue("frame_in")
        nn_out = device.getOutputQueue("nn", maxSize=4, blocking=True)
        
        # Create dai frame
        img = dai.ImgFrame()
        img.setType(dai.ImgFrame.Type.BGR888p)
        img.setWidth(640)
        img.setHeight(640)
        img.setData(cv2.resize(frame_copy, (640, 640)).transpose(2, 0, 1).flatten())
        
        # Start inference
        nn_in.send(img)
        
        # Wait for result with timeout
        start_time = time.time()
        timeout = 2.0  # 2 second timeout
        
        in_nn = None
        while time.time() - start_time < timeout:
            in_nn = nn_out.tryGet()
            if in_nn is not None:
                break
            time.sleep(0.05)
        
        if in_nn is None:
            running_inference = False
            return jsonify({"error": "Detection timeout, no results received from neural network"})
        
        # Process detections
        detections = []
        for detection in in_nn.detections:
            label_id = detection.label
            if label_id < len(labels):
                label_name = labels[label_id]
            else:
                label_name = f"Class {label_id}"
            
            confidence = detection.confidence
            
            if confidence >= confidence_threshold:
                bbox = frameNorm(frame_copy, (detection.xmin, 1-detection.ymax, detection.xmax, 1-detection.ymin))
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
        
        class_counts = {}
        for detection in detections:
            label = detection["label"]
            if label in class_counts:
                class_counts[label] += 1
            else:
                class_counts[label] = 1
        
        running_inference = False
        return jsonify({
            "timestamp": time.time(),
            "detected_classes": class_counts,
            "detections": detections,
            "status": "ok"
        })
    except Exception as e:
        running_inference = False
        return jsonify({
            "error": f"Error processing detections: {str(e)}",
            "status": "error"
        })

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
            .status { padding: 10px; margin-bottom: 10px; border-radius: 4px; display: none; }
            .status.error { background-color: #ffebee; color: #c62828; display: block; }
            .status.warning { background-color: #fff8e1; color: #ff8f00; display: block; }
            .status.success { background-color: #e8f5e9; color: #2e7d32; display: block; }
        </style>
    </head>
    <body>
        <h1>Oak-D Lite Camera Stream</h1>
        <div id="statusMessage" class="status"></div>
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
            const statusMessage = document.getElementById('statusMessage');
            let detectBtnEnabled = true;
            
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
                
                const scaleX = canvas.width / videoStream.naturalWidth;
                const scaleY = canvas.height / videoStream.naturalHeight;
                
                const scaledX = x * scaleX;
                const scaledY = y * scaleY;
                const scaledWidth = width * scaleX;
                const scaledHeight = height * scaleY;
                
                ctx.strokeStyle = '#00FF00';
                ctx.lineWidth = 2;
                ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
                
                ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                ctx.fillRect(scaledX, scaledY - 20, scaledWidth, 20);
                
                ctx.fillStyle = '#FFFFFF';
                ctx.font = '12px Arial';
                ctx.fillText(`${label} (${(confidence * 100).toFixed(0)}%)`, scaledX + 5, scaledY - 5);
            }
            
            document.getElementById('detectBtn').addEventListener('click', function() {
                if (!detectBtnEnabled) return;
                
                detectBtnEnabled = false;
                this.disabled = true;
                statusMessage.textContent = "Processing detection...";
                statusMessage.className = "status warning";
                
                fetch('/detections')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('detectionResults').textContent = JSON.stringify(data, null, 2);
                        
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        
                        if (data.error) {
                            statusMessage.textContent = data.error;
                            statusMessage.className = "status error";
                        } else if (data.detections && data.detections.length > 0) {
                            data.detections.forEach(detection => {
                                drawBoundingBox(detection.bbox, detection.label, detection.confidence);
                            });
                            statusMessage.textContent = `Detection complete. Found ${data.detections.length} objects.`;
                            statusMessage.className = "status success";
                        } else {
                            statusMessage.textContent = "No objects detected.";
                            statusMessage.className = "status warning";
                        }
                        
                        detectBtnEnabled = true;
                        this.disabled = false;
                    })
                    .catch(error => {
                        console.error('Error fetching detections:', error);
                        document.getElementById('detectionResults').textContent = 'Error fetching detections';
                        statusMessage.textContent = "Error connecting to server: " + error.message;
                        statusMessage.className = "status error";
                        detectBtnEnabled = true;
                        this.disabled = false;
                    });
            });
            
            document.getElementById('clearBtn').addEventListener('click', function() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                document.getElementById('detectionResults').textContent = '';
                statusMessage.textContent = "";
                statusMessage.className = "status";
            });
            
            updateCanvasSize();
            
            setInterval(() => {
                const img = document.getElementById('videoStream');
                if (!img.complete || img.naturalWidth === 0 || img.naturalHeight === 0) {
                    statusMessage.textContent = "Camera stream unavailable. Reconnecting...";
                    statusMessage.className = "status error";
                }
            }, 5000);
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8005, debug=False, threaded=True)