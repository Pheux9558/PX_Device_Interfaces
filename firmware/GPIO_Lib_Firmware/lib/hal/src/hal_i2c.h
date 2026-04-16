#pragma once

#include "hal_types.h"

typedef struct {
    uint32_t frequency_hz;
    int16_t scl_pin;
    int16_t sda_pin;
    uint8_t bus;
} hal_i2c_config_t;

hal_status_t hal_i2c_open(uint8_t instance, const hal_i2c_config_t *cfg);
hal_status_t hal_i2c_close(uint8_t instance);
hal_status_t hal_i2c_write(uint8_t instance, uint8_t address, const uint8_t *data, size_t len);
hal_status_t hal_i2c_read(uint8_t instance, uint8_t address, uint8_t *data, size_t len, size_t *out_read);
