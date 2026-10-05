import time
import cv2
from arduino.app_utils import App, Bridge

print("=== Starting Unified Hardware Test Application ===", flush=True)

# 1. Scan I2C
try:
    scan_result = Bridge.call("scan_i2c", timeout=5)
    print(f"[I2C Scan Result] {scan_result}", flush=True)
except Exception as e:
    print(f"[I2C Scan Error] {e}", flush=True)

# 2. Check initial vibration pin state
try:
    vibe_pin = Bridge.call("read_vibe_pin", timeout=2)
    print(f"[Vibration Sensor] Initial D2 state: {'HIGH' if vibe_pin else 'LOW'}", flush=True)
except Exception as e:
    print(f"[Vibration Sensor Error] {e}", flush=True)

# 3. Open USB camera
camera = cv2.VideoCapture(2, cv2.CAP_V4L2)
if not camera.isOpened():
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
if camera.isOpened():
    print(f"[Webcam] Opened successfully via {camera.getBackendName()}", flush=True)
else:
    print("[Webcam] Could not open camera", flush=True)

iteration = 0

def loop():
    global iteration
    iteration += 1

    # 1. Read Vibration Sensor
    vibe_pulses = 0
    try:
        vibe_pulses = Bridge.call("get_vibration", timeout=2)
    except Exception as e:
        print(f"[{iteration}] Vibe read error: {e}", flush=True)

    # 2. Read IMU
    imu_str = "N/A"
    try:
        data = Bridge.call("get_imu", timeout=2)
        if len(data) >= 7 and any(x != 0.0 for x in data):
            ax, ay, az, temp, gx, gy, gz = data[:7]
            imu_str = f"Accel=({ax:+.2f}, {ay:+.2f}, {az:+.2f})g | Gyro=({gx:+.1f}, {gy:+.1f}, {gz:+.1f})°/s | Temp={temp:.1f}°C"
    except Exception as e:
        imu_str = f"Error: {e}"

    # 3. Automated Motor Spin Test Sequence:
    #   Iter 1-4: Motors OFF (measure baseline vibration)
    #   Iter 5-6: Motor A (Left) spins forward gently (PWM 130)
    #   Iter 7-8: Motor B (Right) spins forward gently (PWM 130)
    #   Iter 9+:  Motors OFF
    motor_status = "STOPPED (0, 0)"
    try:
        if iteration in (5, 6):
            Bridge.call("set_motors", 130, 0, timeout=2)
            motor_status = "MOTOR A RUNNING (Speed 130)"
        elif iteration in (7, 8):
            Bridge.call("set_motors", 0, 130, timeout=2)
            motor_status = "MOTOR B RUNNING (Speed 130)"
        elif iteration == 9:
            Bridge.call("set_motors", 0, 0, timeout=2)
            motor_status = "TEST COMPLETE - ALL MOTORS OFF"
        elif iteration > 9:
            motor_status = "IDLE (0, 0)"
    except Exception as e:
        motor_status = f"Motor call error: {e}"

    # 4. Check Webcam frame
    cam_str = "offline"
    if camera.isOpened():
        ret, frame = camera.read()
        cam_str = f"Frame {frame.shape}" if ret else "Read failed"

    print(f"[{iteration:02d}] Motors: {motor_status} | Vibe Pulses: {vibe_pulses} | Webcam: {cam_str} | IMU: {imu_str}", flush=True)

    time.sleep(1)

App.run(user_loop=loop)
