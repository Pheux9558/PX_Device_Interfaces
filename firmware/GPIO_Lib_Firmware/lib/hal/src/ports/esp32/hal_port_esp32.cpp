/**
 * ESP32 HAL Port — concrete implementations for the Arduino/ESP32 framework.
 *
 * Provides: hal_gpio_*, hal_uart_*, hal_time_*
 * backed by pinMode / digitalWrite / analogRead / HardwareSerial / millis.
 *
 * ISR callbacks are wrapped in an IRAM trampoline so callers do not need
 * IRAM_ATTR on their own handler functions.
 */
#if defined(ARDUINO_ARCH_ESP32)

#include <Arduino.h>
#include <HardwareSerial.h>

#include "../../hal_gpio.h"
#include "../../hal_uart.h"
#include "../../hal_time.h"

// ---------------------------------------------------------------------------
// GPIO — digital
// ---------------------------------------------------------------------------

hal_status_t hal_gpio_mode(uint16_t pin, hal_gpio_mode_t mode) {
    switch (mode) {
        case HAL_GPIO_MODE_INPUT:          pinMode((uint8_t)pin, INPUT);          break;
        case HAL_GPIO_MODE_OUTPUT:         pinMode((uint8_t)pin, OUTPUT);         break;
        case HAL_GPIO_MODE_INPUT_PULLUP:   pinMode((uint8_t)pin, INPUT_PULLUP);   break;
        case HAL_GPIO_MODE_INPUT_PULLDOWN: pinMode((uint8_t)pin, INPUT_PULLDOWN); break;
        case HAL_GPIO_MODE_ANALOG:         /* ADC mode is implicit on ESP32 */    break;
        default: return HAL_STATUS_ERROR;
    }
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_write(uint16_t pin, uint8_t value) {
    digitalWrite((uint8_t)pin, value ? HIGH : LOW);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_read(uint16_t pin, uint8_t *value) {
    if (!value) return HAL_STATUS_ERROR;
    *value = (digitalRead((uint8_t)pin) == HIGH) ? 1u : 0u;
    return HAL_STATUS_OK;
}

// ---------------------------------------------------------------------------
// GPIO — analog
// ---------------------------------------------------------------------------

hal_status_t hal_gpio_analog_read(uint16_t pin, uint16_t *value) {
    if (!value) return HAL_STATUS_ERROR;
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

// ---------------------------------------------------------------------------
// GPIO — interrupts
//
// An IRAM trampoline is used so that user callbacks don't need IRAM_ATTR.
// The trampoline itself lives in IRAM and forwards to the stored callback.
// ---------------------------------------------------------------------------

#define HAL_GPIO_MAX_PINS 48u

struct esp32_isr_ctx_t {
    hal_gpio_isr_t cb;
    void          *arg;
};

static esp32_isr_ctx_t g_isr_ctx[HAL_GPIO_MAX_PINS];

static void IRAM_ATTR esp32_isr_trampoline(void *arg) {
    esp32_isr_ctx_t *ctx = reinterpret_cast<esp32_isr_ctx_t *>(arg);
    if (ctx && ctx->cb) {
        ctx->cb(ctx->arg);
    }
}

hal_status_t hal_gpio_attach_isr(uint16_t pin, hal_gpio_isr_t isr, void *arg,
                                  hal_gpio_isr_mode_t mode) {
    if (pin >= HAL_GPIO_MAX_PINS) return HAL_STATUS_ERROR;
    g_isr_ctx[pin].cb  = isr;
    g_isr_ctx[pin].arg = arg;
    int arduino_mode = (mode == HAL_GPIO_ISR_RISING)  ? RISING
                     : (mode == HAL_GPIO_ISR_FALLING) ? FALLING
                     :                                  CHANGE;
    attachInterruptArg((uint8_t)pin, esp32_isr_trampoline,
                       &g_isr_ctx[pin], arduino_mode);
    return HAL_STATUS_OK;
}

hal_status_t hal_gpio_detach_isr(uint16_t pin) {
    detachInterrupt((uint8_t)pin);
    if (pin < HAL_GPIO_MAX_PINS) {
        g_isr_ctx[pin].cb  = nullptr;
        g_isr_ctx[pin].arg = nullptr;
    }
    return HAL_STATUS_OK;
}

// ---------------------------------------------------------------------------
// UART
// ---------------------------------------------------------------------------

static HardwareSerial *uart_hw_serial(uint8_t instance) {
    if (instance == 0) return &Serial1;
    if (instance == 1) return &Serial2;
    return nullptr;
}

hal_status_t hal_uart_open(uint8_t instance, const hal_uart_config_t *cfg) {
    if (!cfg) return HAL_STATUS_ERROR;
    HardwareSerial *s = uart_hw_serial(instance);
    if (!s) return HAL_STATUS_UNSUPPORTED;

    uint32_t config = SERIAL_8N1;
    if (cfg->data_bits == 7) {
        if      (cfg->parity == 1 && cfg->stop_bits == 2) config = SERIAL_7E2;
        else if (cfg->parity == 1)                        config = SERIAL_7E1;
        else if (cfg->parity == 2)                        config = SERIAL_7O1;
        else                                              config = SERIAL_7N1;
    } else {
        if      (cfg->parity == 1 && cfg->stop_bits == 2) config = SERIAL_8E2;
        else if (cfg->parity == 1)                        config = SERIAL_8E1;
        else if (cfg->parity == 2 && cfg->stop_bits == 2) config = SERIAL_8O2;
        else if (cfg->parity == 2)                        config = SERIAL_8O1;
        else if (cfg->stop_bits == 2)                     config = SERIAL_8N2;
        else                                              config = SERIAL_8N1;
    }

    s->begin(cfg->baudrate, config, (int8_t)cfg->rx_pin, (int8_t)cfg->tx_pin);
    return HAL_STATUS_OK;
}

hal_status_t hal_uart_close(uint8_t instance) {
    HardwareSerial *s = uart_hw_serial(instance);
    if (!s) return HAL_STATUS_UNSUPPORTED;
    s->end();
    return HAL_STATUS_OK;
}

hal_status_t hal_uart_write(uint8_t instance, const uint8_t *buf, size_t len,
                             size_t *out_written) {
    HardwareSerial *s = uart_hw_serial(instance);
    if (!s) {
        if (out_written) *out_written = 0;
        return HAL_STATUS_UNSUPPORTED;
    }
    size_t n = s->write(buf, len);
    if (out_written) *out_written = n;
    return HAL_STATUS_OK;
}

hal_status_t hal_uart_read(uint8_t instance, uint8_t *buf, size_t max_len,
                            size_t *out_read) {
    HardwareSerial *s = uart_hw_serial(instance);
    if (!s) {
        if (out_read) *out_read = 0;
        return HAL_STATUS_UNSUPPORTED;
    }
    size_t n = 0;
    while (n < max_len && s->available() > 0) {
        int b = s->read();
        if (b < 0) break;
        buf[n++] = static_cast<uint8_t>(b);
    }
    if (out_read) *out_read = n;
    return HAL_STATUS_OK;
}

// ---------------------------------------------------------------------------
// Time
// ---------------------------------------------------------------------------

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

// Port identity
const char *hal_port_name_esp32(void) {
    return "esp32";
}

#endif  /* ARDUINO_ARCH_ESP32 */
