#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <vector>

#include "display.h"

// provide_safe runs the handler on the loop() thread, so it never races refresh().
static void rpc_draw(std::vector<uint8_t> frame) { display::set_frame(frame.data(), frame.size()); }

void setup() {
    display::init();

    Bridge.begin();
    Bridge.provide_safe("draw", rpc_draw);
}

void loop() {
    display::refresh();
    delay(5);
}
