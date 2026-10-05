# Peripherals Access Guide: Sensors, Camera & Motors

This document details how to access and control the connected peripherals on the Arduino UNO Q ("Imola" Qualcomm QRB2210 + STM32U585 architecture):

1. **MPU6050 6-Axis IMU (Gyro/Accelerometer)** via I2C (`Wire`)
2. **USB Webcam** via Video4Linux2 (`/dev/video2`) and OpenCV
3. **Vibration Switch (HiPi Module)** via Digital GPIO Interrupt (`D2`)
4. **Elegoo V4 DC Gearbox Motors** via TB6612FNG Driver (`D3`, `D5-D10`)

A working application testing all of these components simultaneously is available in the [`sensor-test/`](./sensor-test) directory.

---

## 1. System Architecture Overview

The UNO Q pairs two distinct processing units connected by a high-speed internal UART link managed by `arduino-router`:

```
┌────────────────────────────────────────┐       ┌──────────────────────────────────────┐
│         Qualcomm Linux SoC             │       │        STM32U585 Microcontroller     │
│       Debian 13 (aarch64)              │       │          Zephyr RTOS / Arduino       │
│                                        │       │                                      │
│  - Python applications (Docker/Host)   │       │  - Real-time hardware control        │
│  - USB Host Ports (USB Webcams, Hubs)  │       │  - Header Pins (D0-D21, A0-A5, I2C)  │
│  - Direct device node: /dev/video2     │       │  - Hardware I2C controllers (Wire)   │
│  - High-level AI / Computer Vision     │       │  - Motor PWM timers (D5, D6, D9, D10)│
└───────────────────▲────────────────────┘       └──────────────────▲───────────────────┘
                    │                                               │
                    │               Internal RPC Bridge             │
                    └─────────── [/run/arduino-router.sock] ────────┘
```

---

## 2. Accessing the USB Webcam

### Device Identification & Capabilities
* **USB Identification:** `ID 045e:0811 Microsoft Corp. Microsoft® LifeCam Studio(TM)` (via `lsusb`)
* **V4L2 Nodes:**
  * `/dev/video0`, `/dev/video1`: Internal Qualcomm hardware video decoders/encoders
  * `/dev/video2`: USB Camera **Video Capture** node
  * `/dev/video3`: USB Camera Metadata node
* **Supported Formats:** `MJPG`, `YUYV 4:2:2`, `M420` (tested up to 1080p, default 640x480)

### Reading the Camera in Python (OpenCV)
The base Docker container image (`ghcr.io/arduino/app-bricks/python-apps-base:0.12.0`) includes `opencv-python-headless 4.13.0` by default.

```python
import cv2

# Open /dev/video2 with V4L2 backend
cap = cv2.VideoCapture(2, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Failed to open camera on /dev/video2")
    exit(1)

ret, frame = cap.read()
if ret:
    print(f"Captured frame successfully: shape={frame.shape}")  # (480, 640, 3)

cap.release()
```

---

## 3. Accessing the MPU6050 Gyro / Accelerometer

### Pin Wiring & I2C Bus Mapping
* **VCC:** Breadboard Red Rail (`3V3`)
* **GND:** Breadboard Blue Rail (`GND`)
* **AD0:** Breadboard Blue Rail (`GND`) — sets standard address `0x68`
* **SDA:** Dedicated `SDA` pin (PB11 / D20 in Zephyr DTS)
* **SCL:** Dedicated `SCL` pin (PB10 / D21 in Zephyr DTS)

*(Note: On the Uno Q Zephyr core, dedicated SDA/SCL pins use `Wire`. If wired to A4/A5 instead, the Zephyr core maps those pins to `Wire2`).*

### Microcontroller Reading (`sketch/src/main.cpp`)
The sketch initializes I2C, wakes the MPU6050 from sleep mode (`PWR_MGMT_1` = `0x00`), and exposes `get_imu` via Bridge RPC:

```cpp
#include <Wire.h>
#define MPU6050_ADDR 0x68

static std::vector<float> rpc_get_imu() {
    std::vector<float> data(7, 0.0f);
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(0x3B);
    if (Wire.endTransmission(false) != 0) return data;

    if (Wire.requestFrom((uint8_t)MPU6050_ADDR, (size_t)14) == 14) {
        int16_t ax = (Wire.read() << 8) | Wire.read();
        int16_t ay = (Wire.read() << 8) | Wire.read();
        int16_t az = (Wire.read() << 8) | Wire.read();
        int16_t t  = (Wire.read() << 8) | Wire.read();
        int16_t gx = (Wire.read() << 8) | Wire.read();
        int16_t gy = (Wire.read() << 8) | Wire.read();
        int16_t gz = (Wire.read() << 8) | Wire.read();

        data[0] = (float)ax / 16384.0f;           // Accel X (g)
        data[1] = (float)ay / 16384.0f;           // Accel Y (g)
        data[2] = (float)az / 16384.0f;           // Accel Z (g)
        data[3] = ((float)t / 340.0f) + 36.53f;   // Temperature (°C)
        data[4] = (float)gx / 131.0f;             // Gyro X (°/s)
        data[5] = (float)gy / 131.0f;             // Gyro Y (°/s)
        data[6] = (float)gz / 131.0f;             // Gyro Z (°/s)
    }
    return data;
}
```

---

## 4. Accessing the Vibration Switch (HiPi Module)

### Pin Wiring
* **VCC:** Breadboard Red Rail (`3V3`)
* **GND:** Breadboard Blue Rail (`GND`)
* **SIG:** **UNO Q Pin `D2`**

### Microcontroller Setup
```cpp
#define PIN_VIBE 2
static volatile uint32_t vibe_pulse_count = 0;

static void isr_vibe() {
    vibe_pulse_count++;
}

static int rpc_get_vibration() {
    uint32_t count = vibe_pulse_count;
    vibe_pulse_count = 0; // Reset counter on read
    return (int)count;
}

void setup() {
    pinMode(PIN_VIBE, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_VIBE), isr_vibe, CHANGE);
    Bridge.provide_safe("get_vibration", rpc_get_vibration);
}
```

---

## 5. Controlling the Elegoo V4 Motors (TB6612FNG Driver)

### Power Isolation
* **Motor Power:** Powered by the Elegoo 7.4V battery pack (2x 18650 Li-ion cells).
* **Controller Power:** UNO Q powered via USB-C.
* **Ground:** Connect **Elegoo Shield `GND`** ──► **UNO Q `GND`**. Do **NOT** connect `5V` or `VIN` between the boards.

### Pin Wiring Table

| Elegoo Shield Pin | UNO Q Pin | Function | Notes |
| :--- | :--- | :--- | :--- |
| **GND** | **`GND`** | Common Ground | Essential reference |
| **Pin 3** | **`D3`** | `STBY` (Standby) | Must be `HIGH` to enable motors |
| **Pin 5** | **`D5`** | `PWMA` (Left Speed) | Hardware PWM (0 to 255) |
| **Pin 7** | **`D7`** | `AIN1` (Left Dir A) | Digital Output |
| **Pin 8** | **`D8`** | `AIN2` (Left Dir B) | Digital Output |
| **Pin 6** | **`D6`** | `PWMB` (Right Speed) | Hardware PWM (0 to 255) |
| **Pin 9** | **`D9`** | `BIN1` (Right Dir A) | Digital Output |
| **Pin 10** | **`D10`** | `BIN2` (Right Dir B) | Digital Output |

### Microcontroller Driving Code
```cpp
#define PIN_STBY 3
#define PIN_PWMA 5
#define PIN_PWMB 6
#define PIN_AIN1 7
#define PIN_AIN2 8
#define PIN_BIN1 9
#define PIN_BIN2 10

void set_motors(int left_speed, int right_speed) {
    if (left_speed == 0 && right_speed == 0) {
        digitalWrite(PIN_STBY, LOW);
        analogWrite(PIN_PWMA, 0);
        analogWrite(PIN_PWMB, 0);
        return;
    }

    digitalWrite(PIN_STBY, HIGH);

    // Left Motor (Motor A)
    digitalWrite(PIN_AIN1, left_speed >= 0 ? HIGH : LOW);
    digitalWrite(PIN_AIN2, left_speed >= 0 ? LOW : HIGH);
    analogWrite(PIN_PWMA, constrain(abs(left_speed), 0, 255));

    // Right Motor (Motor B)
    digitalWrite(PIN_BIN1, right_speed >= 0 ? HIGH : LOW);
    digitalWrite(PIN_BIN2, right_speed >= 0 ? LOW : HIGH);
    analogWrite(PIN_PWMB, constrain(abs(right_speed), 0, 255));
}

bool rpc_set_motors(int left, int right) {
    set_motors(left, right);
    return true;
}
```

### Python Motor Control
```python
from arduino.app_utils import Bridge

# Drive forward at half speed
Bridge.call("set_motors", 130, 130)

# Turn in place
Bridge.call("set_motors", 130, -130)

# Stop
Bridge.call("set_motors", 0, 0)
```

---

## 6. Running the Demo Application

The repository contains a fully configured working application in [`sensor-test/`](./sensor-test) that integrates the MPU6050, Webcam, Vibration Switch, and Motors.

### Deploy to Board
From this repository on your local machine:
```bash
./sensor-test/deploy.sh
```

### View Live Logs
```bash
./sensor-test/deploy.sh logs
```

### Verified Live Output (Motors & Vibration In Action)
```text
[01] Motors: STOPPED (0, 0) | Vibe Pulses: 0 | Webcam: Frame (480, 640, 3) | IMU: Accel=(-0.02, -0.05, +1.00)g
[05] Motors: MOTOR A RUNNING (Speed 130) | Vibe Pulses: 0 | Webcam: Frame (480, 640, 3) | IMU: Accel=(-0.03, -0.04, +1.00)g
[07] Motors: MOTOR B RUNNING (Speed 130) | Vibe Pulses: 0 | Webcam: Frame (480, 640, 3) | IMU: Accel=(-0.03, -0.04, +1.03)g
[08] Motors: MOTOR B RUNNING (Speed 130) | Vibe Pulses: 1 | Webcam: Frame (480, 640, 3) | IMU: Accel=(-0.02, -0.05, +0.98)g
[09] Motors: TEST COMPLETE - ALL MOTORS OFF | Vibe Pulses: 0 | Webcam: Frame (480, 640, 3) | IMU: Accel=(-0.03, -0.05, +0.98)g
```
