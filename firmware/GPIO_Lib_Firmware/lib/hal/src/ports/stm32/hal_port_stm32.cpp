#if defined(STM32F1) || defined(STM32F4) || defined(ARDUINO_ARCH_STM32)

#include <Arduino.h>

#include "../../hal_gpio.h"
#include "../../hal_uart.h"
#include "../../hal_time.h"

/*
 * STM32 HAL implementation for Arduino core.
 * GPIO and time are implemented for active services.
 * UART/I2C/SPI can be expanded in follow-up tasks.
 */

hal_status_t hal_gpio_mode(uint16_t pin, hal_gpio_mode_t mode) {
    switch (mode) {
        case HAL_GPIO_MODE_INPUT:
            pinMode((uint8_t)pin, INPUT);
            break;
        case HAL_GPIO_MODE_OUTPUT:
            pinMode((uint8_t)pin, OUTPUT);
            break;
        case HAL_GPIO_MODE_INPUT_PULLUP:
            pinMode((uint8_t)pin, INPUT_PULLUP);
            break;
        case HAL_GPIO_MODE_INPUT_PULLDOWN:
#if defined(INPUT_PULLDOWN)
            pinMode((uint8_t)pin, INPUT_PULLDOWN);
#else
            pinMode((uint8_t)pin, INPUT);
#endif
            break;
        case HAL_GPIO_MODE_ANALOG:
            pinMode((uint8_t)pin, INPUT_ANALOG);
            break;
        default:
            return HAL_STATUS_ERROR;
    }
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_write(uint16_t pin, uint8_t value) {
    digitalWrite((uint8_t)pin, value ? HIGH : LOW);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_read(uint16_t pin, uint8_t *value) {
    if (!value) {
        return HAL_STATUS_ERROR;
    }
    *value = (digitalRead((uint8_t)pin) == HIGH) ? 1u : 0u;
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_analog_read(uint16_t pin, uint16_t *value) {
    if (!value) {
        return HAL_STATUS_ERROR;
    }
    *value = (uint16_t)analogRead((uint8_t)pin);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_analog_write(uint16_t pin, uint16_t value) {
    analogWrite((uint8_t)pin, (int)value);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_analog_resolution(uint8_t bits) {
    analogReadResolution((int)bits);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_attach_isr(uint16_t pin, hal_gpio_isr_t isr, void *arg,
                                 hal_gpio_isr_mode_t mode) {
    (void)pin;
    (void)isr;
    (void)arg;
    (void)mode;
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
    (void)len;
    if (out_written) *out_written = 0;
    return HAL_STATUS_UNSUPPORTED;
}

hal_status_t hal_uart_read(uint8_t instance, uint8_t *buf, size_t max_len, size_t *out_read) {
    (void)instance;
    (void)buf;
    (void)max_len;
    if (out_read) *out_read = 0;
    return HAL_STATUS_UNSUPPORTED;
}

uint32_t hal_time_millis(void) {
    return millis();
}

void hal_time_delay_ms(uint32_t ms) {
    delay(ms);
}

uint32_t hal_time_micros(void) {
    return micros();
}

void hal_time_delay_us(uint32_t us) {
    delayMicroseconds(us);
}

#endif
