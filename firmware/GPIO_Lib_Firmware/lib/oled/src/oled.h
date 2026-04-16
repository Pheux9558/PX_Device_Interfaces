// OLED Display RTOS Service - Phase 4 Implementation
#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void oled_init(void);
const char *oled_module_flags(void);
bool ssd1306_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

#ifdef __cplusplus
}
#endif
