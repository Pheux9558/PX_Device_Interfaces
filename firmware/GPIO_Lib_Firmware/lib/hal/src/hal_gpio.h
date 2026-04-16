#pragma once

#include "hal_types.h"

typedef enum {
    HAL_GPIO_MODE_INPUT = 0,
    HAL_GPIO_MODE_OUTPUT,
    HAL_GPIO_MODE_INPUT_PULLUP,
    HAL_GPIO_MODE_INPUT_PULLDOWN,
    HAL_GPIO_MODE_ANALOG,
} hal_gpio_mode_t;

hal_status_t hal_gpio_mode(uint16_t pin, hal_gpio_mode_t mode);
hal_status_t hal_gpio_write(uint16_t pin, uint8_t value);
hal_status_t hal_gpio_read(uint16_t pin, uint8_t *value);

/* Analog GPIO */
hal_status_t hal_gpio_analog_read(uint16_t pin, uint16_t *value);
hal_status_t hal_gpio_analog_write(uint16_t pin, uint16_t value);
hal_status_t hal_gpio_analog_resolution(uint8_t bits);

/* GPIO interrupt support */
typedef enum {
    HAL_GPIO_ISR_CHANGE  = 0,
    HAL_GPIO_ISR_RISING  = 1,
    HAL_GPIO_ISR_FALLING = 2,
} hal_gpio_isr_mode_t;

typedef void (*hal_gpio_isr_t)(void *arg);

hal_status_t hal_gpio_attach_isr(uint16_t pin, hal_gpio_isr_t isr, void *arg,
                                  hal_gpio_isr_mode_t mode);
hal_status_t hal_gpio_detach_isr(uint16_t pin);
