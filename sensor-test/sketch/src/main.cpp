#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <Wire.h>
#include <vector>

// MPU6050 default I2C address
#define MPU6050_ADDR 0x68
#define MPU6050_ADDR_ALT 0x69

// Vibration Sensor Pin
#define PIN_VIBE 2

// Elegoo TB6612FNG Motor Driver Pins
#define PIN_STBY 3
#define PIN_PWMA 5
#define PIN_PWMB 6
#define PIN_AIN1 7
#define PIN_AIN2 8
#define PIN_BIN1 9
#define PIN_BIN2 10

static TwoWire* active_wire = nullptr;
static uint8_t active_addr = 0;
static volatile uint32_t vibe_pulse_count = 0;

static void isr_vibe() {
    vibe_pulse_count++;
}

static int rpc_get_vibration() {
    uint32_t count = vibe_pulse_count;
    vibe_pulse_count = 0;
    return (int)count;
}

static int rpc_read_vibe_pin() {
    return digitalRead(PIN_VIBE);
}

static void set_motors(int left_speed, int right_speed) {
    if (left_speed == 0 && right_speed == 0) {
        digitalWrite(PIN_STBY, LOW);
        analogWrite(PIN_PWMA, 0);
        analogWrite(PIN_PWMB, 0);
        return;
    }

    digitalWrite(PIN_STBY, HIGH);

    // Motor A (Left)
    if (left_speed >= 0) {
        digitalWrite(PIN_AIN1, HIGH);
        digitalWrite(PIN_AIN2, LOW);
    } else {
        digitalWrite(PIN_AIN1, LOW);
        digitalWrite(PIN_AIN2, HIGH);
    }
    analogWrite(PIN_PWMA, constrain(abs(left_speed), 0, 255));

    // Motor B (Right)
    if (right_speed >= 0) {
        digitalWrite(PIN_BIN1, HIGH);
        digitalWrite(PIN_BIN2, LOW);
    } else {
        digitalWrite(PIN_BIN1, LOW);
        digitalWrite(PIN_BIN2, HIGH);
    }
    analogWrite(PIN_PWMB, constrain(abs(right_speed), 0, 255));
}

static bool rpc_set_motors(int left_speed, int right_speed) {
    set_motors(left_speed, right_speed);
    return true;
}

static String rpc_scan_i2c() {
    String result = "";

    // Scan Wire
    result += "Wire (D20/D21 SDA/SCL): [";
    Wire.begin();
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            char buf[8];
            snprintf(buf, sizeof(buf), "0x%02X ", addr);
            result += buf;
        }
    }
    result += "] | ";

    // Scan Wire2
    result += "Wire2 (D18/D19 A4/A5): [";
    Wire2.begin();
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire2.beginTransmission(addr);
        if (Wire2.endTransmission() == 0) {
            char buf[8];
            snprintf(buf, sizeof(buf), "0x%02X ", addr);
            result += buf;
        }
    }
    result += "]";

    return result;
}

static bool init_mpu6050() {
    Wire2.begin();
    Wire2.beginTransmission(MPU6050_ADDR);
    if (Wire2.endTransmission() == 0) {
        active_wire = &Wire2;
        active_addr = MPU6050_ADDR;
    } else {
        Wire2.beginTransmission(MPU6050_ADDR_ALT);
        if (Wire2.endTransmission() == 0) {
            active_wire = &Wire2;
            active_addr = MPU6050_ADDR_ALT;
        }
    }

    if (!active_wire) {
        Wire.begin();
        Wire.beginTransmission(MPU6050_ADDR);
        if (Wire.endTransmission() == 0) {
            active_wire = &Wire;
            active_addr = MPU6050_ADDR;
        } else {
            Wire.beginTransmission(MPU6050_ADDR_ALT);
            if (Wire.endTransmission() == 0) {
                active_wire = &Wire;
                active_addr = MPU6050_ADDR_ALT;
            }
        }
    }

    if (!active_wire) {
        return false;
    }

    active_wire->beginTransmission(active_addr);
    active_wire->write(0x6B);
    active_wire->write(0x00);
    return (active_wire->endTransmission() == 0);
}

static std::vector<float> rpc_get_imu() {
    std::vector<float> imu(7, 0.0f);
    if (!active_wire) {
        if (!init_mpu6050()) {
            return imu;
        }
    }

    active_wire->beginTransmission(active_addr);
    active_wire->write(0x3B);
    if (active_wire->endTransmission(false) != 0) {
        return imu;
    }

    if (active_wire->requestFrom((uint8_t)active_addr, (size_t)14) == 14) {
        int16_t ax = (active_wire->read() << 8) | active_wire->read();
        int16_t ay = (active_wire->read() << 8) | active_wire->read();
        int16_t az = (active_wire->read() << 8) | active_wire->read();
        int16_t t  = (active_wire->read() << 8) | active_wire->read();
        int16_t gx = (active_wire->read() << 8) | active_wire->read();
        int16_t gy = (active_wire->read() << 8) | active_wire->read();
        int16_t gz = (active_wire->read() << 8) | active_wire->read();

        imu[0] = (float)ax / 16384.0f;
        imu[1] = (float)ay / 16384.0f;
        imu[2] = (float)az / 16384.0f;
        imu[3] = ((float)t / 340.0f) + 36.53f;
        imu[4] = (float)gx / 131.0f;
        imu[5] = (float)gy / 131.0f;
        imu[6] = (float)gz / 131.0f;
    }

    return imu;
}

void setup() {
    // 1. Vibration sensor setup on D2
    pinMode(PIN_VIBE, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_VIBE), isr_vibe, CHANGE);

    // 2. Motor driver setup
    pinMode(PIN_STBY, OUTPUT);
    pinMode(PIN_PWMA, OUTPUT);
    pinMode(PIN_PWMB, OUTPUT);
    pinMode(PIN_AIN1, OUTPUT);
    pinMode(PIN_AIN2, OUTPUT);
    pinMode(PIN_BIN1, OUTPUT);
    pinMode(PIN_BIN2, OUTPUT);
    set_motors(0, 0); // Start in safe, stopped state

    // 3. Register Bridge RPCs
    Bridge.begin();
    Bridge.provide_safe("scan_i2c", rpc_scan_i2c);
    Bridge.provide_safe("get_imu", rpc_get_imu);
    Bridge.provide_safe("get_vibration", rpc_get_vibration);
    Bridge.provide_safe("read_vibe_pin", rpc_read_vibe_pin);
    Bridge.provide_safe("set_motors", rpc_set_motors);

    init_mpu6050();
}

void loop() {
}
