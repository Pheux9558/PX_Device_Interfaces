#pragma once
#include <stdint.h>

// Initialize board module (registers build flags)
void board_init();

// Return board flag string (statically allocated)
const char *board_module_flags();

// Board-specific FastLED configuration (if board has onboard addressable LED)
// These are defined per-board and can be used by other modules (e.g. debug)
#if defined(BOARD) && (BOARD == ESP32_T_DONGLE_S3)
    // T-Dongle-S3 has APA102 (DotStar) LED with clock and data pins
    #define BOARD_HAS_FASTLED 1
    #define BOARD_FASTLED_DATA_PIN 40
    #define BOARD_FASTLED_CLOCK_PIN 39
    #define BOARD_FASTLED_TYPE 0x00  // APA102
    #define BOARD_FASTLED_COUNT 1
#endif

// Add more boards here as needed
// Example:
// #if defined(BOARD) && (BOARD == ESP32_PICO_D4)
//     #define BOARD_HAS_FASTLED 1
//     #define BOARD_FASTLED_DATA_PIN 8
//     #define BOARD_FASTLED_CLOCK_PIN 0xFFFF  // no clock for WS2812
//     #define BOARD_FASTLED_TYPE 0x01  // WS2812
//     #define BOARD_FASTLED_COUNT 1
// #endif
