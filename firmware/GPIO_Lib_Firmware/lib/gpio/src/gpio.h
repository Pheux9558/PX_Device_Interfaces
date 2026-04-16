// GPIO RTOS Service - Phase 3 Task Implementation
// GpioTask: timer-driven polling of digital and analog inputs
// Handles command dispatch and owns all GPIO state
#pragma once

#include <stdint.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

// Initialize GPIO task system and register command handlers
void gpio_init(void);

// Legacy function (kept for compatibility, now calls gpio_send_digital_update internally)
void gpio_poll_inputs(void);

// Command handler: processes GPIO commands (setup, read, write)
// Returns true if command was handled, false otherwise
bool gpio_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

// Module info string
const char *gpio_module_flags(void);

#ifdef __cplusplus
}
#endif
