# rpi4

- camera-stream.service `journalctl -u camera-stream.service -f` (192.168.2.220:1883 pi4/detections) (http://192.168.2.220:8005/video_stream)
- gyro-mqtt.service `journalctl -u gyro-mqtt.service` (192.168.2.220:1883 pi4/gyro)
- vibration-motor-controller.service `journalctl -u vibration-motor-controller.service` (192.168.8.220:5000/vibrate)  (192.168.8.220:1883 pi4/vibration_motor_controller)

```
curl -X POST http://localhost:5000/vibrate \
  -H "Content-Type: application/json" \
  -d '{"left_duration": 0.5, "right_duration": 0.5}'

{
    "data": {
        "left_duration": 0.5,
        "right_duration": 0.5
    },
    "message": "Vibration command sent",
    "status": "success"
}
```