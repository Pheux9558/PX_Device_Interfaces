# GPIO_Lib_Firmware_RTOS - Clean RTOS Architecture

This folder contains the FreeRTOS-based refactoring of the GPIO Library firmware, starting fresh from a clean RTOS-first architecture.

## Directory Structure

### Core RTOS Infrastructure

- **lib/rtosal/** - RTOS Abstraction Layer (FreeRTOS wrapper for board independence)
- **lib/hal/** - Hardware Abstraction Layer (GPIO, UART, I2C, SPI, Timing)
- **lib/serial_rtos/** - FreeRTOS-based serial transport (RxTask, TxTask, command/response queues)

### Foundational Modules (Active)

- **lib/board/** - Board initialization and configuration
- **lib/cmd/** - Command definitions and protocol constants
- **lib/serial/** - Low-level serial I/O (unified Arduino interface)
- **lib/modules/** - Module registry system
- **lib/firmware/** - Firmware-level commands and diagnostics
- **lib/debug/** - Debug output and heartbeat (optional)
- **lib/compat/** - Compatibility shims (SPI/serial conflict resolution)

### Service Modules (Phase 2-4 Implementation Placeholders)

Each of these will be rewritten with FreeRTOS tasks in subsequent phases:

- **lib/gpio/**     → Phase 2 (GpioTask - digital/analog I/O)
- **lib/uart/**     → Phase 3 (UARTTask - per-instance UART management)
- **lib/i2c/**      → Phase 4 (I2CTask - I2C master/slave)
- **lib/spi/**      → Phase 4 (SPITask - SPI master/slave)
- **lib/lcd/**      → Phase 4 (DisplayTask - ST7735, HD44780, AIP31068L)
- **lib/oled/**     → Phase 4 (OLEDTask - SSD1306)
- **lib/fastled/**  → Phase 4 (LEDTask - WS2812, APA102)
- **lib/matrix/**   → Phase 4 (MatrixTask - UNO R4 LED matrix)

### Legacy Reference (Archive)

- **lib/_legacy/** - Original implementations of services listed above (for reference during Phase 2-4 rewrites, then delete)

## Phase Roadmap

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1 | RTOSAL, HAL, serial_rtos scaffolding | ✓ Complete |
| Phase 1.1 | Implement serial_rtos with RxTask/TxTask, DispatchTask | In Progress |
| Phase 1A | Board bring-up on ESP32-S3-R8 and STM32F411 | Pending |
| Phase 2 | GPIO service rewrite with GpioTask | Pending |
| Phase 3 | UART service rewrite with UARTTask | Pending |
| Phase 4 | I2C, SPI, Display, FastLED services | Pending |
| Phase 5 | System monitoring, reliability, performance | Pending |
| Phase 6 | Remove legacy code, finalize architecture | Pending |

## Building

```bash
# Default ESP32 target
pio run -e esp32_s3_r8

# STM32 target
pio run -e stm32f411

# Upload
pio run -t upload --upload-port /dev/ttyACM0
```

## Design Principles

1. **RTOS-first**: All I/O and business logic runs in FreeRTOS tasks, not main loop polling
2. **Clean abstraction layers**: RTOSAL hides board-specific RTOS details; HAL hides peripheral details
3. **Queue-driven**: Inter-task communication via FreeRTOS queues, not globals
4. **Maximum throughput**: GPIO and UART priority = HIGH (task priority 3)
5. **Backward compatible**: Host API remains unchanged; internal architecture redesigned
6. **Testable**: MockTransport validates protocol compliance; board validation via bring-up matrix

## Porting from GPIO_Lib_Firmware

The original GPIO_Lib_Firmware is preserved as reference. To migrate a service:

1. Study the old implementation in `lib/_legacy/{service}`
2. Implement the new task-based version in `lib/{service}` following the RTOSAL + HAL model
3. Update cmd handler to queue work to the task, not execute inline
4. Test with existing host MockTransport tests
5. Delete the _legacy version once validated

## Key Files

- [FREERTOS_REWORK.md](FREERTOS_REWORK.md) - Detailed architecture and design decisions
- [src/main.cpp](src/main.cpp) - Entry point (will be minimal once tasks handle everything)
- [lib/rtosal/src/rtosal.h](lib/rtosal/src/rtosal.h) - RTOS abstraction API
- [lib/hal/src/hal_types.h](lib/hal/src/hal_types.h) - HAL status and config types
- [lib/serial_rtos/src/serial_rtos.h](lib/serial_rtos/src/serial_rtos.h) - Transport layer API
