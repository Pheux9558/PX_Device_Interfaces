#pragma once
#include <stdint.h>
#include <stdbool.h>

void oled_init();
const char *oled_module_flags();

// SSD1306 OLED handler (0x005x)
bool ssd1306_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
