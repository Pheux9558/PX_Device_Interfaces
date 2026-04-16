#include "hal_gpio.h"
#include "hal_i2c.h"
#include "hal_spi.h"
#include "hal_time.h"
#include "hal_uart.h"

/* Stub implementations — only compiled when no real port is active.        */
/* ESP32 and STM32 are served by their respective hal_port_*.cpp files.     */
#if !defined(ARDUINO_ARCH_ESP32) && !defined(ARDUINO_ARCH_STM32)

hal_status_t hal_gpio_mode(uint16_t pin, hal_gpio_mode_t mode) {
    (void)pin;
    (void)mode;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_write(uint16_t pin, uint8_t value) {
    (void)pin;
    (void)value;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_read(uint16_t pin, uint8_t *value) {
    (void)pin;
    if (value) *value = 0;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_analog_read(uint16_t pin, uint16_t *value) {
    (void)pin;
    if (value) *value = 0;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_analog_write(uint16_t pin, uint16_t value) {
    (void)pin;
    (void)value;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_analog_resolution(uint8_t bits) {
    (void)bits;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_attach_isr(uint16_t pin, hal_gpio_isr_t isr, void *arg,
                                  hal_gpio_isr_mode_t mode) {
    (void)pin; (void)isr; (void)arg; (void)mode;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_gpio_detach_isr(uint16_t pin) {
    (void)pin;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_uart_open(uint8_t instance, const hal_uart_config_t *cfg) {
    (void)instance;
    (void)cfg;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_uart_close(uint8_t instance) {
    (void)instance;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_uart_write(uint8_t instance, const uint8_t *buf, size_t len, size_t *out_written) {
    (void)instance;
    (void)buf;
    if (out_written) *out_written = 0;
    (void)len;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_uart_read(uint8_t instance, uint8_t *buf, size_t max_len, size_t *out_read) {
    (void)instance;
    (void)buf;
    (void)max_len;
    if (out_read) *out_read = 0;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_i2c_open(uint8_t instance, const hal_i2c_config_t *cfg) {
    (void)instance;
    (void)cfg;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_i2c_close(uint8_t instance) {
    (void)instance;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_i2c_write(uint8_t instance, uint8_t address, const uint8_t *data, size_t len) {
    (void)instance;
    (void)address;
    (void)data;
    (void)len;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_i2c_read(uint8_t instance, uint8_t address, uint8_t *data, size_t len, size_t *out_read) {
    (void)instance;
    (void)address;
    (void)data;
    (void)len;
    if (out_read) *out_read = 0;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_spi_open(uint8_t instance, const hal_spi_config_t *cfg) {
    (void)instance;
    (void)cfg;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_spi_close(uint8_t instance) {
    (void)instance;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_spi_transfer(uint8_t instance, const uint8_t *tx, uint8_t *rx, size_t len, size_t *out_transferred) {
    (void)instance;
    (void)tx;
    (void)rx;
    (void)len;
    if (out_transferred) *out_transferred = 0;
    return HAL_STATUS_UNSUPPORTED;
}

uint32_t hal_time_millis(void) {
    return 0;
}

void hal_time_delay_ms(uint32_t ms) {
    (void)ms;
}

uint32_t hal_time_micros(void) {
    return 0;
}

void hal_time_delay_us(uint32_t us) {
    (void)us;
}

#endif /* !ARDUINO_ARCH_ESP32 && !ARDUINO_ARCH_STM32 */
