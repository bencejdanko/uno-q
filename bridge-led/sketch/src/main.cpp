#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#include "led.h"

// RPC handlers. provide_safe runs them on the main loop thread, so they may touch
// hardware safely -- keep loop() non-blocking or they will be delayed.
static bool rpc_toggle_led() { return led::toggle(); }
static void rpc_set_led(bool on) { led::set(on); }
static bool rpc_get_led() { return led::get(); }

void setup() {
    led::init();

    Bridge.begin();
    Bridge.provide_safe("toggle_led", rpc_toggle_led);
    Bridge.provide_safe("set_led", rpc_set_led);
    Bridge.provide_safe("get_led", rpc_get_led);
}

void loop() {
    // Real-time work (motor control, sensors) goes here; never block for long.
}
