# rpi2

- buttons/main.py --> pi2/button_state, 192.168.2.219:1883 (button-monitor.service)
- gyro/main.py --> pi2/gyro, 192.168.2.219:1883 (gyro-monitor.service)
- vibration_motors/main.py --> pi2/vibration_motor_response 192.168.2.219:1883 (vibration-motors.service)
- pitch_yaw_roll/main.py --> pi2/pitch_yaw_roll, 192.168.2.219:1883 (pitch-yaw-roll.service) endpoint /calibrate