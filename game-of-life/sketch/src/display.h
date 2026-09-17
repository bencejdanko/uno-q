#pragma once

#include <cstddef>
#include <cstdint>

namespace display {

constexpr uint8_t ROWS = 8;
constexpr uint8_t COLS = 13;

void init();
// Stores a row-major ROWS*COLS frame of brightness levels 0..7; shorter input is zero-padded.
void set_frame(const uint8_t* data, size_t len);
// Pushes the latest frame to the matrix if it changed. Call from loop().
void refresh();

}  // namespace display
