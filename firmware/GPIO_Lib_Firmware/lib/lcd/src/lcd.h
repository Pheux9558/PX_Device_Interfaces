// LCD Service (Phase 4 bootstrap)
// ST7735 path is implemented first; other display families remain as stubs.
#pragma once

#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void lcd_init(void);
bool st7735_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
bool hd44780_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
bool aip31068l_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *lcd_module_flags(void);

#ifdef __cplusplus
}
#endif
