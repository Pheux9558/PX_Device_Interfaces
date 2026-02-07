#pragma once
#include <stdint.h>

// Initialize FastLED module (register flags/allocations)
void fastled_init();

// Command handler for FastLED command range
bool fastled_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

// Return module flags string (copied by modules_add_flag)
const char *fastled_module_flags();

// Public constants for LED types (match host enum)
#define FASTLED_TYPE_APA102 0x00
#define FASTLED_TYPE_WS2812 0x01

