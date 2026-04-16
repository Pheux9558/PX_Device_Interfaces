// I2C Service (Phase 4 bootstrap)
// Provides command handling for I2C create/config/read/write/scan.
#pragma once

#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>

#if defined(ARDUINO)
#include <Wire.h>
#endif

void i2c_init(void);
bool i2c_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *i2c_module_flags(void);

#if defined(ARDUINO)
typedef struct {
	uint16_t id;
	uint8_t wire_id;  // 0 for Wire, 1 for Wire1
	TwoWire *wire;
	int8_t scl;
	int8_t sda;
	uint32_t freq;
	bool used;
} i2c_instance_t;

i2c_instance_t *i2c_get_instance(uint16_t id);
#endif
