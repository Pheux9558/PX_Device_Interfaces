#pragma once
#include <stdint.h>
#include <stdbool.h>

void lcd_init();
bool lcd_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *lcd_module_flags();
