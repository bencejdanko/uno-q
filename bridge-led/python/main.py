# Runs on the Linux side (MPU). Calls functions the MCU exposes via Bridge.provide*.
import time

from arduino.app_utils import App, Bridge


def loop():
    state = Bridge.call("toggle_led", timeout=2)  # returns the new LED state from the MCU
    print(f"LED is now {'ON' if state else 'OFF'}", flush=True)
    time.sleep(1)


App.run(user_loop=loop)
