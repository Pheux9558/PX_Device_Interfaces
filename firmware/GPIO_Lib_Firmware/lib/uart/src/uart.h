#pragma once
#include <stdint.h>
#include <stdbool.h>

#if defined(ARDUINO)
#include <Arduino.h>
#endif

void uart_init();
bool uart_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *uart_module_flags();
