#pragma once

#include "hal_types.h"

typedef struct {
    uint32_t frequency_hz;
    uint8_t mode;
    int16_t sck_pin;
    int16_t mosi_pin;
    int16_t miso_pin;
} hal_spi_config_t;

hal_status_t hal_spi_open(uint8_t instance, const hal_spi_config_t *cfg);
hal_status_t hal_spi_close(uint8_t instance);
hal_status_t hal_spi_transfer(uint8_t instance, const uint8_t *tx, uint8_t *rx, size_t len, size_t *out_transferred);
