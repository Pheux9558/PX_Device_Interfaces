#pragma once
#include <stdint.h>
#include <stdbool.h>

// Firmware info module
bool firmware_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *firmware_module_flags();
