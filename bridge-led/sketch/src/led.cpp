#include "led.h"

#include <Arduino.h>

namespace led {
namespace {
bool state = false;

void write() {
    digitalWrite(LED_BUILTIN, state ? LOW : HIGH);  // UNO Q user LED is active-low
}
}  // namespace

void init() {
    pinMode(LED_BUILTIN, OUTPUT);
    write();
}

void set(bool on) {
    state = on;
    write();
}

bool toggle() {
    set(!state);
    return state;
}

bool get() { return state; }

}  // namespace led
