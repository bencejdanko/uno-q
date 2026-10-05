# Instructions

## Running App Lab Examples

1. Install Arduino App Lab (Installs all required CLI tools)
2. Add `export PATH="$HOME/.arduino15/packages/arduino/tools/adb/32.0.0:$PATH"` to `.bashrc`

This gives you access to `adb`, Android Debug Bridge.

```
adb --help

# Show the connected devices
adb devices

# Connect to the device shell
adb shell
```

Alternatively, you can SSH in:

```
ssh arduino@gatos.local
```

## Hardware & Sensors Documentation

- [MPU6050 Pinout & Wiring](MPU6050.md)
- [Peripherals Access Guide (MPU6050 Gyro & USB Webcam)](PERIPHERALS.md)
- [Sensor Test Demo Application](sensor-test/)
