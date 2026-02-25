#pragma once
#include <stdint.h>
#include <stdbool.h>

void lcd_init();
const char *lcd_module_flags();

// ST7735 LCD handler (0x002x)
bool st7735_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

// HD44780 character LCD handler (0x003x)
bool hd44780_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

// AiP31068L character LCD handler (0x004x)
bool aip31068l_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
