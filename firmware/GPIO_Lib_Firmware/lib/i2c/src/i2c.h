#pragma once
#include <stdint.h>
#include <stdbool.h>

#if defined(ARDUINO)
#include <Wire.h>
#endif

void i2c_init();
bool i2c_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *i2c_module_flags();

#if defined(ARDUINO)
struct i2c_instance_t {
    uint16_t id;
    TwoWire *wire;
    int8_t scl;
    int8_t sda;
    uint32_t freq;
    bool used;
};

i2c_instance_t *i2c_get_instance(uint16_t id);
#endif
