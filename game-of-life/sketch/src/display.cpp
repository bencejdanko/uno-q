#include "display.h"

#include <Arduino_LED_Matrix.h>
#include <cstring>

namespace display {
namespace {
Arduino_LED_Matrix matrix;
uint8_t frame[ROWS * COLS] = {0};
bool dirty = false;
}  // namespace

void init() {
    matrix.begin();
    matrix.setGrayscaleBits(3);  // brightness 0..7
    matrix.clear();
}

void set_frame(const uint8_t* data, size_t len) {
    size_t n = len < sizeof(frame) ? len : sizeof(frame);
    memcpy(frame, data, n);
    memset(frame + n, 0, sizeof(frame) - n);
    dirty = true;
}

void refresh() {
    if (!dirty) return;
    matrix.draw(frame);
    dirty = false;
}

}  // namespace display
