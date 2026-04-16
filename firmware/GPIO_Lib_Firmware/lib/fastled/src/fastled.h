#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void fastled_init(void);
bool fastled_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *fastled_module_flags(void);

#define FASTLED_TYPE_APA102 0x00
#define FASTLED_TYPE_WS2812 0x01

bool fastled_set_single_led(uint16_t instance_id, uint8_t r, uint8_t g, uint8_t b);
bool fastled_create_debug_instance(uint16_t instance_id, uint16_t data_pin, uint16_t clock_pin, uint8_t led_type);

#ifdef __cplusplus
}
#endif
