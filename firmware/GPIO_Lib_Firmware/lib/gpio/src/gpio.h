// GPIO HAL header
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif


void gpio_init();
void gpio_digital_write(uint16_t pin, uint8_t value);
int gpio_digital_read(uint16_t pin);
void gpio_analog_write(uint16_t pin, uint16_t value);
int gpio_analog_read(uint16_t pin);

// Setup helpers
// mode: 0 = INPUT, 1 = OUTPUT
void gpio_set_mode(uint16_t pin, uint8_t mode);
// pull: 0 = NONE, 1 = PULLUP, 2 = PULLDOWN
void gpio_set_pull(uint16_t pin, uint8_t pull);
// attach a servo to a pin (index can be used by higher-level code)
void gpio_attach_servo(uint16_t pin, uint8_t index);

// Debug callback: firmware can call this to notify host or log events.
// Signature: function receives a null-terminated C string message.
typedef void (*gpio_debug_cb_t)(const char *msg);
void gpio_set_debug_cb(gpio_debug_cb_t cb);

// Command handler exported by the GPIO module. Returns true if it handled
// the command (and sent any responses), false otherwise.
bool gpio_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

// Module info string used by CMD_FIRMWARE_BUILD_FLAGS aggregation
const char *gpio_module_flags();

#ifdef __cplusplus
}
#endif
