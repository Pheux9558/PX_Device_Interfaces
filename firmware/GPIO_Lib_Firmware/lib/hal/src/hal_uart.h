#pragma once

#include "hal_types.h"

typedef struct {
    uint32_t baudrate;
    uint8_t data_bits;
    uint8_t parity;
    uint8_t stop_bits;
    uint8_t flow_control;
    int16_t tx_pin;
    int16_t rx_pin;
} hal_uart_config_t;

hal_status_t hal_uart_open(uint8_t instance, const hal_uart_config_t *cfg);
hal_status_t hal_uart_close(uint8_t instance);
hal_status_t hal_uart_write(uint8_t instance, const uint8_t *buf, size_t len, size_t *out_written);
hal_status_t hal_uart_read(uint8_t instance, uint8_t *buf, size_t max_len, size_t *out_read);
