// UART RTOS Service - Phase 3 Implementation Placeholder
// This module will be rewritten with FreeRTOS task-based implementation in Phase 3
// Legacy implementation moved to lib/_legacy/uart for reference
#pragma once

#include <stdint.h>
#include <stdlib.h>

#if defined(ARDUINO_ARCH_STM32)
// STM32 core headers (e.g. HardwareSerial.h) include "uart.h" expecting the
// core's UART types (serial_t, etc.). Our project header has the same name,
// so pull the next uart.h from the include path to preserve core definitions.
#if defined(__has_include_next)
#if __has_include_next("uart.h")
#include_next "uart.h"
#endif
#endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

void gpio_uart_init(void);
	bool uart_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

#ifdef __cplusplus
}
#endif
