import cv2
import depthai as dai
import numpy as np
import time
import json
import base64
from flask import Flask, Response, jsonify, request
import threading
import uuid as uuid4
import paho.mqtt.client as mqtt
import gc
from queue import Queue, Empty

MQTT_HOST = '0.0.0.0'
MQTT_PORT = 1883
MQTT_TOPIC_DETECTIONS = 'pi4/detections'
MQTT_TOPIC_DEPTH_MAP = 'pi4/depth_map'
MQTT_TOPIC_DETECTION_IMAGE = 'pi4/detection_image'

mqtt_message_queue = Queue(maxsize=20)

try:
    with open('yolov8ntrained.json', 'r') as f:
        model_config = json.load(f)
    labels = model_config['mappings']['labels']
    confidence_threshold = 0.6
except Exception as e:
    print(f"Error loading model config: {e}")
    model_config = {}
    labels = []
    confidence_threshold = 0.6

app = Flask(__name__)

last_detection_time = 0
DETECTION_COOLDOWN = 1.0

latest_frame = None
latest_depth = None
device = None
frame_lock = threading.Lock()
depth_lock = threading.Lock()
running_inference = False
app_running = True

def create_pipeline():
    pipeline = dai.Pipeline()
    
    camRgb = pipeline.create(dai.node.ColorCamera)
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoRight = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)
    detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
    
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xinFrame = pipeline.create(dai.node.XLinkIn)
    nnOut = pipeline.create(dai.node.XLinkOut)
    xoutDepth = pipeline.create(dai.node.XLinkOut)
    
    xoutRgb.setStreamName("rgb")
    xinFrame.setStreamName("frame_in")
    nnOut.setStreamName("nn")
    xoutDepth.setStreamName("depth")
    
    camRgb.setPreviewSize(640, 640)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camRgb.setFps(15)
    
    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)
    
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(False)
    
    if hasattr(model_config, 'get') and model_config.get('nn_config'):
        try:
            detectionNetwork.setBlobPath("yolov8ntrained_openvino_2022.1_6shave.blob")
            detectionNetwork.setConfidenceThreshold(confidence_threshold)
            detectionNetwork.setNumClasses(model_config['nn_config']['NN_specific_metadata']['classes'])
            detectionNetwork.setCoordinateSize(model_config['nn_config']['NN_specific_metadata']['coordinates'])
            detectionNetwork.setAnchors([])
            detectionNetwork.setAnchorMasks({})
            detectionNetwork.setIouThreshold(model_config['nn_config']['NN_specific_metadata']['iou_threshold'])
            detectionNetwork.setNumInferenceThreads(2)
            detectionNetwork.input.setBlocking(False)
        except Exception as e:
            print(f"Error configuring detection network: {e}")
    
    monoLeft.out.link(stereo.left)
    monoRight.out.link(stereo.right)
    
    camRgb.preview.link(xoutRgb.input)
    stereo.depth.link(xoutDepth.input)
    
    xinFrame.out.link(detectionNetwork.input)
    detectionNetwork.out.link(nnOut.input)
    
    return pipeline

def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

def create_placeholder_frame(message="Connecting to camera..."):
    frame = np.zeros((320, 480, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = message
    textsize = cv2.getTextSize(text, font, 0.8, 1)[0]
    text_x = (frame.shape[1] - textsize[0]) // 2
    text_y = (frame.shape[0] + textsize[1]) // 2
    cv2.putText(frame, text, (text_x, text_y), font, 0.8, (255, 255, 255), 1)
    
    if "in use" in message.lower():
        instruction = "Please close other applications using the camera"
        inst_size = cv2.getTextSize(instruction, font, 0.4, 1)[0]
        inst_x = (frame.shape[1] - inst_size[0]) // 2
        inst_y = text_y + 30
        cv2.putText(frame, instruction, (inst_x, inst_y), font, 0.4, (255, 255, 255), 1)
    
    return frame

def calculate_distance(depth_map, bbox):
    try:
        x1, y1, x2, y2 = bbox
        
        x1 = max(0, min(x1, depth_map.shape[1] - 1))
        y1 = max(0, min(y1, depth_map.shape[0] - 1))
        x2 = max(0, min(x2, depth_map.shape[1] - 1))
        y2 = max(0, min(y2, depth_map.shape[0] - 1))
        
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        
        sample_size = 10
        x_start = max(center_x - sample_size//2, 0)
        y_start = max(center_y - sample_size//2, 0)
        x_end = min(center_x + sample_size//2, depth_map.shape[1])
        y_end = min(center_y + sample_size//2, depth_map.shape[0])
        
        if x_end > x_start and y_end > y_start:
            depth_slice = depth_map[y_start:y_end, x_start:x_end]
            
            if depth_slice.size > 0:
                valid_depths = depth_slice[depth_slice > 0]
                
                if len(valid_depths) > 0:
                    median_depth = np.median(valid_depths)
                    return median_depth / 1000.0
        
        return None
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None

def mqtt_worker():
    global app_running
    
    print("Starting MQTT worker thread")
    
    mqtt_client = mqtt.Client()
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start()
        
        while app_running:
            try:
                message = mqtt_message_queue.get(timeout=1.0)
                topic, payload = message
                
                mqtt_client.publish(topic, payload)
                mqtt_message_queue.task_done()
                
                time.sleep(0.01)
                
            except Empty:
                pass
            except Exception as e:
                print(f"Error in MQTT worker: {e}")
                time.sleep(1)
    
    except Exception as e:
        print(f"Error setting up MQTT client: {e}")
    
    finally:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except:
            pass
        
        print("MQTT worker thread stopped")

def publish_message(topic, message):
    try:
        if not mqtt_message_queue.full():
            mqtt_message_queue.put_nowait((topic, message))
        else:
            print(f"MQTT queue full, dropping message to {topic}")
    except Exception as e:
        print(f"Error adding message to MQTT queue: {e}")

def run_pipeline():
    global latest_frame, latest_depth, device, app_running
    
    print("Starting pipeline thread")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    device_in_use = False
    last_reconnect_time = 0
    reconnect_cooldown = 5
    
    while app_running:
        try:
            if device_in_use:
                with frame_lock:
                    latest_frame = create_placeholder_frame("Camera in use by another application")
                time.sleep(5)
                device_in_use = False
                consecutive_errors = 0
                continue
            
            current_time = time.time()
            if current_time - last_reconnect_time < reconnect_cooldown:
                time.sleep(1)
                continue
            
            last_reconnect_time = current_time
            print("Creating pipeline and connecting to device")
            
            pipeline = create_pipeline()
            device = dai.Device(pipeline)
            
            qRgb = device.getOutputQueue(name="rgb", maxSize=2, blocking=False)
            qDepth = device.getOutputQueue(name="depth", maxSize=2, blocking=False)
            
            print("Starting video stream...")
            consecutive_errors = 0
            
            while app_running:
                try:
                    inRgb = qRgb.tryGet()
                    if inRgb is not None:
                        frame = inRgb.getCvFrame()
                        frame = cv2.flip(frame, 0)
                        
                        with frame_lock:
                            latest_frame = frame.copy()
                    
                    if np.random.random() < 0.3:
                        inDepth = qDepth.tryGet()
                        if inDepth is not None:
                            depth_frame = inDepth.getFrame()
                            if latest_frame is not None:
                                target_size = (latest_frame.shape[1] // 2, latest_frame.shape[0] // 2)
                                depth_frame = cv2.resize(depth_frame, target_size)
                            
                            with depth_lock:
                                latest_depth = depth_frame.copy()
                    
                    if np.random.random() < 0.01:
                        gc.collect()
                    
                    time.sleep(0.05)
                
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
            time.sleep(5)
        
        except Exception as e:
            print(f"Error during device initialization: {e}")
            consecutive_errors += 1
            time.sleep(5)
        
        print("Attempting to reconnect to device...")
        
        try:
            if device is not None:
                device.close()
                device = None
        except Exception as e:
            print(f"Error closing device: {e}")
    
    print("Pipeline thread stopped")

def generate_frames():
    global latest_frame, app_running
    
    last_frame_time = 0
    frame_interval = 0.05
    
    while app_running:
        try:
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.05)
                continue
            
            last_frame_time = current_time
            current_frame = None
            
            with frame_lock:
                if latest_frame is not None:
                    current_frame = latest_frame.copy()
                else:
                    current_frame = create_placeholder_frame()
            
            scale_factor = 0.5
            current_frame = cv2.resize(current_frame, 
                                      (int(current_frame.shape[1] * scale_factor), 
                                       int(current_frame.shape[0] * scale_factor)))
            
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            ret, buffer = cv2.imencode('.jpg', current_frame, encode_params)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
            if np.random.random() < 0.2:
                gc.collect()
        
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            placeholder = create_placeholder_frame("Error generating frame")
            ret, buffer = cv2.imencode('.jpg', placeholder)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.5)

def visualize_depth(depth_frame):
    small_depth = cv2.resize(depth_frame, (320, 240))
    depth_colormap = cv2.normalize(small_depth, None, 0, 255, cv2.NORM_MINMAX)
    depth_colormap = cv2.applyColorMap(depth_colormap.astype(np.uint8), cv2.COLORMAP_JET)
    return depth_colormap

def draw_detections(frame, detections):
    result_frame = frame.copy()
    
    colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), 
              (0, 255, 255), (255, 0, 255), (128, 128, 0), (0, 128, 128)]
    
    for i, detection in enumerate(detections):
        label = detection["label"]
        confidence = detection["confidence"]
        bbox = detection["bbox"]
        
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        
        color_idx = i % len(colors)
        color = colors[color_idx]
        
        cv2.rectangle(result_frame, (x1, y1), (x2, y2), color, 2)
        
        label_text = f"{label}: {confidence:.2f}"
        
        cv2.putText(result_frame, label_text, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        if "distance" in detection:
            distance_text = f"{detection['distance']:.2f}m"
            cv2.putText(result_frame, distance_text, (x1, y2 + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    return result_frame

def frame_to_base64(frame, quality=70):
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buffer = cv2.imencode('.jpg', frame, encode_params)
    if not success:
        return None
    
    encoded_image = base64.b64encode(buffer).decode('utf-8')
    return encoded_image

@app.route('/video_stream')
def video_stream():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detections')
def get_detections():
    global latest_frame, latest_depth, device, running_inference, last_detection_time
    
    current_time = time.time()
    if current_time - last_detection_time < DETECTION_COOLDOWN:
        return jsonify({
            "error": "Rate limit exceeded, please wait before requesting more detections",
            "status": "rate_limited"
        })
    
    last_detection_time = current_time
    
    if latest_frame is None:
        return jsonify({"error": "No frame available"})
    
    if device is None:
        return jsonify({"error": "Camera device not initialized", "status": "disconnected"})
    
    if running_inference:
        return jsonify({"error": "Detection already in progress", "status": "busy"})
    
    running_inference = True
    
    try:
        placeholder_check = np.sum(latest_frame[:, :, 0]) + np.sum(latest_frame[:, :, 1]) + np.sum(latest_frame[:, :, 2])
        if placeholder_check < 10000:
            running_inference = False
            return jsonify({
                "error": "Camera not available or in use by another application", 
                "status": "unavailable",
                "detections": []
            })
        
        frame_copy = None
        depth_copy = None
        
        with frame_lock:
            if latest_frame is not None:
                frame_copy = latest_frame.copy()
            else:
                running_inference = False
                return jsonify({"error": "No frame available for detection"})
        
        with depth_lock:
            if latest_depth is not None:
                depth_copy = latest_depth.copy()
        
        try:
            nn_in = device.getInputQueue("frame_in", maxSize=1, blocking=False)
            nn_out = device.getOutputQueue("nn", maxSize=1, blocking=True)
            
            img = dai.ImgFrame()
            img.setType(dai.ImgFrame.Type.BGR888p)
            img_size = 640
            img.setWidth(img_size)
            img.setHeight(img_size)
            
            resized_frame = cv2.resize(frame_copy, (img_size, img_size))
            img.setData(resized_frame.transpose(2, 0, 1).flatten())
            
            nn_in.send(img)
            
            start_time = time.time()
            timeout = 1.0
            
            in_nn = None
            while time.time() - start_time < timeout:
                in_nn = nn_out.tryGet()
                if in_nn is not None:
                    break
                time.sleep(0.05)
            
            if in_nn is None:
                running_inference = False
                return jsonify({"error": "Detection timeout", "status": "timeout"})
            
            detections = []
            for detection in in_nn.detections:
                label_id = detection.label
                if label_id < len(labels):
                    label_name = labels[label_id]
                else:
                    label_name = f"Class {label_id}"
                
                confidence = detection.confidence
                
                if confidence >= confidence_threshold:
                    bbox = frameNorm(frame_copy, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                    
                    distance = None
                    if depth_copy is not None:
                        distance = calculate_distance(depth_copy, (bbox[0], bbox[1], bbox[2], bbox[3]))
                    
                    detection_data = {
                        "label": label_name,
                        "confidence": float(confidence),
                        "bbox": {
                            "x1": int(bbox[0]),
                            "y1": int(bbox[1]),
                            "x2": int(bbox[2]),
                            "y2": int(bbox[3])
                        }
                    }
                    
                    if distance is not None:
                        detection_data["distance"] = round(float(distance), 2)
                    
                    detections.append(detection_data)
            
            detection_image = None
            depth_map = None
            detection_image_b64 = None
            depth_map_b64 = None
            
            detections = detections[:10]
            
            if frame_copy is not None and detections:
                small_frame = cv2.resize(frame_copy, (480, 320))
                detection_image = draw_detections(small_frame, detections)
                detection_image_b64 = frame_to_base64(detection_image, quality=65)
                
            if depth_copy is not None and detections:
                depth_map = visualize_depth(depth_copy)
                depth_map_b64 = frame_to_base64(depth_map, quality=60)
            
            class_counts = {}
            for detection in detections:
                label = detection["label"]
                if label in class_counts:
                    class_counts[label] += 1
                else:
                    class_counts[label] = 1
            
            running_inference = False
            
            result = {
                'status': 'ok',
                "timestamp": time.time(),
                "num_detections": len(detections),
                "detections": detections,
            }
            
            if detection_image_b64:
                result["detection_image"] = detection_image_b64
            
            if depth_map_b64:
                result["depth_map"] = depth_map_b64
            
            if detections:
                unique_id = str(uuid4.uuid4())
                
                publish_message(MQTT_TOPIC_DETECTIONS, json.dumps({
                    "timestamp": time.time(),
                    "id": unique_id,
                    "num_detections": len(detections),
                    "detections": detections
                }))
                
                if np.random.random() < 0.3 and detection_image_b64:
                    publish_message(MQTT_TOPIC_DETECTION_IMAGE, json.dumps({
                        "timestamp": time.time(),
                        "id": unique_id,
                        "detection_image": detection_image_b64
                    }))
                    
                if np.random.random() < 0.2 and depth_map_b64:
                    publish_message(MQTT_TOPIC_DEPTH_MAP, json.dumps({
                        "timestamp": time.time(),
                        "id": unique_id,
                        "depth_map": depth_map_b64
                    }))
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Error during neural network inference: {e}")
            running_inference = False
            return jsonify({
                "error": f"Error during neural network inference: {str(e)}",
                "status": "error"
            })
            
    except Exception as e:
        print(f"Error processing detections: {e}")
        running_inference = False
        return jsonify({
            "error": f"Error processing detections: {str(e)}",
            "status": "error"
        })

@app.route('/')
def visualization():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Stream</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .video-container { margin-bottom: 20px; }
            .controls { margin-bottom: 20px; }
            button { padding: 8px 16px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Camera Stream</h1>
            <div class="video-container">
                <img src="/video_stream" width="640" height="480" />
            </div>
            <div class="controls">
                <button onclick="detectObjects()">Detect Objects</button>
            </div>
            <div id="detection-results"></div>
        </div>
        
        <script>
            function detectObjects() {
                document.getElementById('detection-results').innerHTML = 'Detecting objects...';
                
                fetch('/detections')
                    .then(response => response.json())
                    .then(data => {
                        if(data.error) {
                            document.getElementById('detection-results').innerHTML = 
                                `<p>Error: ${data.error}</p>`;
                            return;
                        }
                        
                        let resultsHtml = `<h2>Detected ${data.num_detections} objects</h2>`;
                        
                        if(data.detection_image) {
                            resultsHtml += `<img src="data:image/jpeg;base64,${data.detection_image}" width="640" />`;
                        }
                        
                        if(data.detections && data.detections.length > 0) {
                            resultsHtml += '<ul>';
                            data.detections.forEach(detection => {
                                resultsHtml += `<li>${detection.label} (${(detection.confidence * 100).toFixed(1)}%)`;
                                if(detection.distance) {
                                    resultsHtml += ` - Distance: ${detection.distance.toFixed(2)}m`;
                                }
                                resultsHtml += '</li>';
                            });
                            resultsHtml += '</ul>';
                        }
                        
                        document.getElementById('detection-results').innerHTML = resultsHtml;
                    })
                    .catch(error => {
                        document.getElementById('detection-results').innerHTML = 
                            `<p>Error communicating with server: ${error}</p>`;
                    });
            }
        </script>
    </body>
    </html>
    """

def cleanup():
    global app_running, device
    
    print("Cleaning up resources...")
    
    app_running = False
    
    if device is not None:
        try:
            device.close()
        except:
            pass
    
    print("Cleanup complete")

if __name__ == "__main__":
    try:
        with frame_lock:
            latest_frame = create_placeholder_frame()
        
        mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
        mqtt_thread.start()
        
        pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        pipeline_thread.start()
        
        app.run(host='0.0.0.0', port=8005, debug=False, threaded=True)
    
    except KeyboardInterrupt:
        print("KeyboardInterrupt received, shutting down...")
    
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        cleanup()