# FreeRTOS Rework - Architecture and Portability Plan

## Executive Summary

**Status: Phase 4 Complete & Validated** ✅

The FreeRTOS rework has transitioned from architecture design and task infrastructure (Phases 1–3) to full peripheral service implementation and performance validation (Phase 4). All core systems are functional on ESP32-S3-R8 with production-quality implementations of GPIO, UART, I2C, SPI, display services (LCD ST7735, OLED SSD1306), and FastLED services (APA102 + WS2812) validated on hardware.

**Key Achievements:**
- ✅ Task-based architecture with O(1) command dispatch and self-registration complete
- ✅ All Phase 4 core peripherals implemented: SPI, LCD ST7735, OLED SSD1306, FastLED (I2C already complete)
- ✅ Performance validated: 100% packet success rate, sub-millisecond latency (0.297ms avg), zero timeouts
- ✅ Memory footprint remains low after service bring-up: Flash 10.7%, RAM 10.6%
- ✅ Hardware stability: 15+ seconds stable operation with no watchdog timeouts or crashes

**Next Focus:** STM32F411 portability validation, Arduino Uno R4 WiFi support planning for Matrix, extended reliability testing, then finalize Phase 6 legacy cleanup.

## Goals

| Priority | Goal |
|----------|------|
| 1 | Maximum throughput / minimum latency on GPIO and UART |
| 2 | Clean service boundaries - one task = one responsibility |
| 3 | Retain the existing host API calling convention |
| 4 | New, extensible command-dispatch design |
| 5 | Strong portability across ESP32 and STM32 first |
| 6 | Robust error handling - task failures never brick the system |

## Platform Strategy

Primary target families:
- `ESP32` / `ESP32-S3` using Arduino-on-ESP32 with native FreeRTOS underneath.
- `STM32` using STM32duino or STM32Cube-based builds with FreeRTOS enabled.

Secondary targets:
- `Renesas RA` / `UNO R4` kept as a compatibility target.
- `AVR` stays legacy-only unless a reduced non-RTOS path is kept.

Implications:
- The architecture is designed first for ESP32 and STM32 performance and driver models.
- FreeRTOS use must be wrapped behind an RTOS abstraction layer.
- Peripheral access must be wrapped behind a uniform HAL layer.
- Board-specific quirks must never leak into command handlers or service logic.

## Supported Board Families

| Family | Priority | Notes |
|--------|----------|-------|
| `ESP32` | P0 | First reference platform. Best path to prove the task model and throughput goals. |
| `STM32` | P0 | Second reference platform. Should validate that abstractions are not ESP-specific. |
| `Renesas RA / UNO R4` | P1 | Keep support, but do not let it drive the architecture. |
| `AVR` | P3 | Legacy support only. Likely stays on an older code path. |

Recommended first-class boards:
- ESP32 reference board: `ESP32-S3-R8`.
- STM32 reference board: `STM32F411`.

Reference board profiles (frozen for phase 1-3):

| Family | Board | Purpose |
|--------|-------|---------|
| `ESP32` | `ESP32-S3-R8` | Primary performance baseline and first implementation target |
| `STM32` | `STM32F411` | Portability baseline and second implementation target |

## Current Architecture (what we are migrating from)

```text
setup()
  serial_begin(921600)
  module_init() x N
  cmd_init() + cmd_register_handler() x N

loop()
  bytes = serial_read_all()
  cmd_process_bytes(bytes)
  gpio_poll_inputs()
  matrix_update()
  delay(calc_delay())
```

Current problems:
- Single-threaded: UART work blocks GPIO polling and vice versa.
- `calc_delay()` introduces idle latency.
- `cmd_process_bytes()` uses a flat linear scan of handlers.
- Global mutable module state has no concurrency protection.
- Blocking transport writes stall the whole system.
- Board-specific assumptions are mixed into the same layers as protocol logic.

## New Architecture

The external model stays the same:
- Host creates a communication interface.
- Host creates a peripheral object.
- The peripheral uses the selected interface for communication.

Only the internal firmware execution model changes.

### Task map

```text
ISR / DMA
  -> Rx wakeup / ring buffer
  -> RxTask

RxTask
  -> cmd_queue
  -> DispatchTask

DispatchTask
  -> gpio_queue  -> GpioTask
  -> uart_queue  -> UartTask
  -> i2c_queue   -> I2cTask
  -> spi_queue   -> SpiTask
  -> display_queue -> DisplayTask

Service tasks
  -> response_queue
  -> TxTask
```

### Tasks and responsibilities

| Task | Priority | Responsibility |
|------|----------|----------------|
| `RxTask` | High | Read raw bytes from the transport HAL, frame packets, validate checksum, emit command messages |
| `DispatchTask` | High | O(1) command lookup, route commands to the correct service task |
| `TxTask` | High | Own the TX path and serialize outgoing responses |
| `GpioTask` | Normal | GPIO setup, writes, input polling, change reporting |
| `UartTask` | Normal | UART instance lifecycle, transmit, receive, buffering |
| `I2cTask` | Normal | I2C command execution |
| `SpiTask` | Normal | SPI command execution |
| `SysMonTask` | Low | Error counters, watchdog, service health, restart policy |

Fast-path rule:
- `GPIO` and `UART` are priority one for speed.
- Their tasks may use notifications plus preallocated buffers to minimize copies and queue overhead.

## RTOS Abstraction Layer

To support multiple FreeRTOS ports with one firmware architecture, add `RTOSAL`.

```c
// lib/rtosal/src/rtosal.h
typedef void *rtosal_task_t;
typedef void *rtosal_queue_t;
typedef void *rtosal_mutex_t;
typedef uint32_t rtosal_tick_t;

typedef enum {
    RTOSAL_OK = 0,
    RTOSAL_TIMEOUT,
    RTOSAL_FULL,
    RTOSAL_EMPTY,
    RTOSAL_ERROR,
} rtosal_status_t;

rtosal_status_t rtosal_task_create(...);
rtosal_status_t rtosal_queue_create(...);
rtosal_status_t rtosal_queue_send(...);
rtosal_status_t rtosal_queue_receive(...);
rtosal_status_t rtosal_notify_give(...);
rtosal_status_t rtosal_notify_take(...);
rtosal_status_t rtosal_mutex_create(...);
rtosal_status_t rtosal_mutex_lock(...);
rtosal_status_t rtosal_mutex_unlock(...);
void rtosal_delay_until(rtosal_tick_t *last_wake, rtosal_tick_t period);
rtosal_tick_t rtosal_now_ticks(void);
```

Rules:
- Service code uses `rtosal_*` only.
- No service code calls native FreeRTOS APIs directly.
- No service code depends on ESP-IDF, STM HAL, Arduino core internals, or Renesas APIs directly.

Planned RTOSAL ports:
- `rtosal_freertos_common.c`
- `rtosal_esp32.cpp`
- `rtosal_stm32.cpp`
- `rtosal_renesas.cpp`

Why this matters:
- ESP32 and STM32 can use different ISR, DMA, and task pinning semantics without changing service code.
- We can later add a host/native simulation backend for unit tests.
- Low-end compatibility shims remain possible.

## Uniform HAL Layer

Add a board-independent hardware abstraction layer above vendor drivers and below services.

```c
// lib/hal/src/hal_gpio.h
hal_status_t hal_gpio_mode(uint16_t pin, hal_gpio_mode_t mode);
hal_status_t hal_gpio_write(uint16_t pin, uint8_t value);
hal_status_t hal_gpio_read(uint16_t pin, uint8_t *value);

// lib/hal/src/hal_uart.h
hal_status_t hal_uart_open(uint8_t inst, const hal_uart_config_t *cfg);
hal_status_t hal_uart_write(uint8_t inst, const uint8_t *buf, size_t len);
hal_status_t hal_uart_read(uint8_t inst, uint8_t *buf, size_t max_len, size_t *out_len);
```

Layer boundaries:
- `cmd` layer: packet parsing, validation, dispatch.
- `service` layer: GPIO/UART/I2C/SPI/display logic.
- `HAL` layer: hardware operations.
- `RTOSAL` layer: tasks, queues, mutexes, notifications.

Directory target structure:

```text
lib/
  rtosal/
    src/
      rtosal.h
      rtosal_freertos_common.c
      rtosal_esp32.cpp
      rtosal_stm32.cpp
      rtosal_renesas.cpp
  hal/
    src/
      hal_gpio.h
      hal_uart.h
      hal_i2c.h
      hal_spi.h
      hal_time.h
      ports/
        esp32/
        stm32/
        renesas/
```

## Command Dispatch - New Design

Current problem:
- `cmd_register_handler()` stores command ranges and walks them linearly.
- Adding a new library requires touching central startup code.

New design:

```c
typedef struct {
    uint16_t cmd;
    cmd_handler_fn_t fn;
    uint8_t service_id;
} cmd_entry_t;

void cmd_dispatch_init(void);
bool cmd_dispatch_lookup(uint16_t cmd, cmd_entry_t *out);
```

Refinement:
- Exact command lookup in O(1) average time using a compact hash table.
- Modules self-register commands through a macro such as `CMD_REGISTER(cmd, service, fn)`.
- Routing is split into two steps:
  - `cmd -> service endpoint`
  - `service endpoint -> queue or fast-path`
- Command ranges remain protocol-level only, not board-level.

Speed rules:
- Tiny hot-path commands should avoid heap allocation.
- `GPIO` and `UART` can use service-local fast-path wakeups via task notifications.
- Large display and LED transfers use pooled buffers.

## Inter-task Communication

| Object | Type | Purpose |
|--------|------|---------|
| `cmd_queue` | Queue | `RxTask -> DispatchTask` |
| `gpio_queue` | Queue | `DispatchTask -> GpioTask` |
| `uart_queue` | Queue | `DispatchTask -> UartTask` |
| `i2c_queue` | Queue | `DispatchTask -> I2cTask` |
| `spi_queue` | Queue | `DispatchTask -> SpiTask` |
| `response_queue` | Queue | `Any service -> TxTask` |
| `tx_mutex` | Mutex | Protects direct transport/banner writes when unavoidable |
| `service_notify[N]` | Task notifications | Low-overhead wakeup for single-consumer hot paths |
| `uart_inst_mutex[N]` | Mutex | Per-UART-instance access protection |

Message model:

```c
#define CMD_INLINE_PAYLOAD 64

typedef struct {
    uint16_t cmd;
    uint16_t len;
    uint8_t payload[CMD_INLINE_PAYLOAD];
    uint8_t *heap_payload;
} cmd_msg_t;
```

Allocation strategy:
- Static queues and task stacks whenever possible.
- Inline payload for small packets.
- Pool allocator for large payloads.
- No general-purpose heap usage on the hot path for `GPIO` and `UART`.

## Serial / Transport Layer

`RxTask` replaces the current polling in `loop()`.

Board-family transport notes:
- `ESP32`: prefer ISR or DMA receive and task notification to `RxTask`.
- `STM32`: prefer HAL/LL interrupt or DMA receive into a ring buffer, then wake `RxTask`.
- `USB CDC` targets: isolate CDC behavior in transport HAL code only.

`TxTask` owns TX exclusively:
- Services never call transport writes directly in normal operation.
- Responses go through `response_queue`.
- `TxTask` handles backpressure, timeouts, and drop policy.

## Error Handling and Stability

| Scenario | Action |
|----------|--------|
| Queue full | Increment overflow counter, optionally drop oldest or reject newest, emit error response where possible |
| Bad checksum | Drop packet, increment checksum counter |
| Unknown command | Return protocol error |
| Stack overflow | Trigger stack overflow hook and system recovery path |
| Pool allocation failure | Drop request, increment memory error counter, report error |
| Service timeout | Mark service degraded or faulted |

Add a per-service health state:
- `INIT`
- `READY`
- `DEGRADED`
- `FAULTED`

Add system diagnostics command:
- `CMD_SYS_GET_STATS (0xFFFA)` for queue depth, error counters, service states, and transport metrics.

## Host API - What Changes

The calling convention remains the same:

```python
uart = gpio_lib.UART(gpio_lib, tx_pin=1, rx_pin=2, baudrate=115200)
uart.setup()
uart.write(b"hello")
```

Allowed host-side changes:
- Extend transport config objects with capability reporting if useful.
- Add optional feature discovery so the host can adapt to board limits.
- Add diagnostics/statistics commands without changing the public object model.

## Migration Phases

### Phase 1 - Foundation
- [x] Add `RTOSAL` skeleton and define the common API.
- [x] Add `HAL` skeleton for GPIO/UART/I2C/SPI/time.
- [x] Add first-class ESP32 and STM32 build targets.
- [x] Implement `serial_rtos.c/h` with `RxTask`, `TxTask`, `response_queue`, task/queue lifecycle.
- [x] Replace direct `serial_write()` response generation with queued TX in cmd handlers.
- [x] Remove `calc_delay()` and global idle delays from the main execution path.
- [x] Update main() to call serial_rtos_begin() and block for DispatchTask to process cmd_queue.

### Phase 1A - Code cleanup and board bring-up validation
- [x] Remove legacy service implementations and archive to `lib/_legacy/` for reference.
- [x] Create minimal service stubs for all libraries (gpio, uart, i2c, spi, lcd, oled, fastled, matrix).
- [x] Build cleanly on ESP32-S3-R8 with RTOSAL/HAL stubs - **COMPLETE** (Flash: 7.9%, RAM: 7.3%).
- [x] Build cleanly on STM32F411 with RTOSAL/HAL stubs.
- [x] Validate boot sequence and GPIO_READY banner on ESP32 and STM32.
  - [x] ESP32 validated on hardware (`/dev/ttyACM0`, T-Dongle-S3) with `GPIO_READY` banner.
  - [x] STM32 validated on hardware (`/dev/ttyACM0`, BlackPill via STLink) with GPIO smoke test (pinMode, digital_write HIGH/LOW all OK).
- [x] Confirm no runtime crashes from stub implementations.
  - [x] ESP32 stable after RTOSAL stack-size/queue fixes (no RxTask overflow in latest run).
  - [x] STM32 stable on hardware; GPIO commands processed without errors.

### Phase 1A - Board bring-up matrix
- [x] Bring up `ESP32-S3-R8` first. **COMPLETE** — Hardware validated on `/dev/ttyACM0` (T-Dongle-S3 variant) with GPIO_READY banner, 15+ seconds stable uptime, all services tested with example scripts.
- [x] Bring up `STM32F411` second. **COMPLETE** — Hardware validated on BlackPill via STLink; GPIO commands (pinMode, digital_write) verified on hardware; flash 5.9%, RAM 11.4%.
- [ ] Keep Renesas compiling through a compatibility port. **PENDING**
- [ ] Decide whether AVR remains a frozen legacy branch. **PENDING**

### Phase 2 - Dispatch redesign
- [x] Implement real ESP32 `RTOSAL` backend for tasks, queues, mutexes, notifications, and timing.
- [x] Fix queued dispatch handoff (`cmd_queue` frame -> `cmd_process_bytes` full packet).
- [x] Route `cmd_send_response()` through queued TX path (`serial_write_rtos`) with direct-write fallback.
- [x] Implement `cmd_dispatch.c/h` with O(1) hash-table lookup (Phase 2.5).
- [x] Replace range-scan handler registration with hash-table (fallback to legacy scan for ranges spanning multiple high-bytes).
- [x] Add self-registration macros for service commands.
- [x] Migrate GPIO and UART first.

**Phase 2.5 Completion Note:**
- Implemented hash-table dispatch using command high-byte (0x00-0xFF) as hash index
- All commands in range 0x00xx-0x0Fxx map to one entry per high-byte byte value (256 entries total)
- Lookup: O(1) via `cmd_dispatch_lookup(cmd)`, falls back to legacy range-scan if needed
- Hardware validated on `/dev/ttyACM0` (T-Dongle-S3): GPIO_READY detected with no errors
- Build metrics: Flash 8.0%, RAM 9.5% (slight increase from previous build, still comfortable)

**Phase 2 Self-Registration Completion Note:**
- Added `lib/cmd/src/cmd_auto.h` — `CMD_REGISTER(start, end, fn)` macro
- Added `lib/cmd/src/cmd_auto.cpp` — singly-linked list (`g_head`) built via `__attribute__((constructor(101)))` before `setup()`
- `cmd_init()` now calls `cmd_auto_register_all()` after `cmd_dispatch_init()` to process all declared handlers
- Migrated all 11 service handler registrations out of `main.cpp`:
  - `gpio_cmd_handler` (0x0000-0x001F) — self-registers in `gpio.cpp`
  - `uart_cmd_handler` (0x0200-0x020F) — self-registers in `uart.cpp`
  - `firmware_cmd_handler` (0xFFFC-0xFFFF) — self-registers in `firmware.cpp` (legacy path, spans high-bytes)
  - `i2c/spi/lcd/oled/fastled/matrix` stubs — each self-registers in their own `.cpp` with matching build-flag guards
- `main.cpp` `dispatch_init()` + `cmd_init()` is now a two-liner with no command-range knowledge
- Hardware validated: all GPIO and UART commands ACK correctly via self-registered handlers
- Build metrics: Flash 9.1% (303,905 bytes), RAM 10.2% (33,432 bytes)

### Phase 3 - Service tasks
- [x] Implement `GpioTask` with timer-driven polling using `rtosal_delay_until()`.
- [x] Implement `UartTask` with per-instance protection and optional RX buffering.
- [x] Move service state ownership into the owning task.
- [x] Move vendor-specific code fully behind HAL ports.

**Phase 3.1 GPIO Task Completion Note:**
- Implemented timer-driven GPIO polling using `rtosal_delay_until()` for precise 10ms intervals
- GpioTask owns all GPIO state: `digital_input_t[16]`, `analog_input_t[8]`, thresholds
- Command handler processes GPIO setup/read/write commands from DispatchTask
- Interrupt-driven digital input support (ESP32 ISR path) with polling fallback
- Fixed timer initialization: `wake_time = rtosal_now_ticks()` (not offset) for proper periodic behavior
- Task priority: 1 (below dispatch @ priority 3, above idle @ priority 0)
- Hardware validated on `/dev/ttyACM0` (T-Dongle-S3): 15+ seconds stable uptime, no watchdog timeout
- Memory impact: Flash 8.5% (283,917 bytes), RAM 9.9% (32,488 bytes) - reasonable headroom for Phase 4

**Phase 3.3 Service State Ownership Completion Note:**
- Bundled scattered file-scope globals into `gpio_state_t` (GPIO) and `uart_state_t` (UART) structs
- Both tasks now created with `&g_<service>_state` as the task `arg`; `task_fn(void *arg)` casts the arg and owns all state through that pointer
- Added `RTOSAL_MAX_DELAY` sentinel to `rtosal.h` (maps to `portMAX_DELAY` in the ESP32 backend)
- Added `g_gpio_mutex` and `g_uart_mutex` created in service init; acquired by cmd handlers (DispatchTask context) before touching shared state, and by service task loops before polling — eliminates state races between DispatchTask and service tasks
- Hardware validated on T-Dongle-S3 via `show_rgb565_file.py`: 89 OK frames, 13.87 KB/s, no errors
- Memory impact: Flash 10.7%, RAM 10.6% (unchanged — no heap increase)

**Phase 3.2 UART Task Completion Note:**
- Implemented task-based per-instance UART management with RX ring buffering
- UARTTask owns per-instance state: tx_pin, rx_pin, baudrate, data_bits, parity, stop_bits, flow_control
- RX ring buffer (256 bytes per instance) polled at 10ms intervals, filled from HardwareSerial
- Command handlers for all 10 UART commands (0x0200-0x020A) with full parameter support
- ESP32 HardwareSerial support: dual UART instances (Serial1, Serial2) with hardware pin mapping
- Task priority: 1 (normal, alongside GpioTask)
- Stack allocation: 4096 words (16KB) for UART I/O and ring buffer management
- Hardware validated on `/dev/ttyACM0` (T-Dongle-S3): Both instances created, configured, and writing successfully
- Test scenario: 
  - Instance 0: 115200 baud, 8-N-1, pins 17/18
  - Instance 1: 9600 baud, 7-E-1, pins 1/2
  - Both instances received ACK for all configuration and write commands
  - No task crash, no stack overflow, stable operation
- Memory impact: Flash 9.1% (305,229 bytes, +1.6% from Phase 3.1), RAM 10.2% (33,384 bytes, +0.3%)
- Build time: 5.75 seconds, successful upload and execution

### Phase 4 - Remaining services
- [x] I2C service (commands 0x0210–0x021E) — already implemented and functional from Phase 3 work.
- [x] SPI service (commands 0x0220–0x0227) — full-duplex transfers, per-instance frequency/mode/pin config.
- [x] LCD ST7735 service (commands 0x0020–0x002C) — RGB565 streaming, bitmap transfers, WRITE_TEXT/WRITE_TEXT_CENTER, backlight, rotation.
- [x] OLED SSD1306 service (commands 0x0050–0x005B) — dual I2C/SPI backend, text, bitmap streaming (mono), brightness, rotation.
- [x] FastLED RGB LED service (APA102 + WS2812 command handling ported and hardware smoke tested on ESP32-S3-R8).
- [ ] Encoder service (0x0310-0x0313) implemented with `EncoderTask` polling, position tracking, and direction detection.
- [ ] Stepper service (0x0320-0x0328) implemented with `StepperTask`, trapezoidal speed profile, and status reporting.
- [ ] Matrix service remains deferred pending Arduino Uno R4 WiFi platform integration.

**Phase 4 Completion Note:**
- Ported all SPI, LCD, OLED, and FastLED service implementations from `lib/_legacy/` to production locations
- Build flags added to platformio.ini: `-DLCD_SUPPORT`, `-DOLED_SUPPORT`, `-DFASTLED_SUPPORT` (SPI and I2C already enabled)
- Tested with host examples:
  - `show_rgb565_file.py`: ST7735 display renders 80×80 RGB565 images successfully
  - `color_format_test.py`: ST7735 renders 8 color patterns with text labels (WRITE_TEXT), 202 OK frames
  - `oled_test.py`: SSD1306 full test sequence (rotations, brightness sweep, bitmap), 154 OK frames
- FastLED status:
  - APA102 and WS2812 command handlers ported into `lib/fastled/src/fastled.cpp`
  - ESP32-S3-R8 build passes with `FASTLED_SUPPORT` enabled
  - Hardware smoke validated with host scripts (`px_device_interfaces/tests/test_FastLed.py` and `px_device_interfaces/examples/WS2812.py`)
- Memory impact after enabling FastLED on ESP32-S3-R8: Flash 10.7%, RAM 10.6%
- Encoder + Stepper services are now implemented in the active firmware tree and build for both ESP32-S3-R8 and STM32F411.
- STM32F411 hardware smoke validated command path via USB CDC (`/dev/ttyACM0`) using new host examples:
  - `px_device_interfaces/examples/encoder/encoder_test.py` (PA0/PA1)
  - `px_device_interfaces/examples/stepper/stepper_test.py` (PA2..PA7)
- Matrix remains the only deferred service because it depends on Arduino Uno R4 WiFi integration.
- Matrix is not a generic Phase 4 follow-up for ESP32/STM32; it depends on adding Arduino Uno R4 WiFi platform support first

### Phase 5 - Reliability and performance
- [ ] Add `SysMonTask`.
- [ ] Add pool allocator and queue depth instrumentation.
- [ ] Add service restart policy where safe.
- [x] Benchmark throughput and latency on ESP32 and STM32 (Intel gathering phase).

**Phase 5 Performance Benchmark (Initial):**
- Performance test runner: `plot_is_should.py` (captures timestamped firmware debug logs)
- Test scenario: 100 GPIO blink cycles on pin 10 via `blink_builtin.py` with `require_ack_on_send=True`
- Results:
  - **Send packets:** 202 total
  - **Device ACKs:** 202 total (100% success rate, 0 packet loss)
  - **Send → receive latency:** avg 0.297ms, median 0.0ms
  - **Max hardware delay threshold:** 10ms (0 packets exceeded)
  - **Total test duration:** ~2.3 seconds
- Graph analysis: Send and OK curves overlap tightly; latency spikes only at startup (~5ms), then flat near zero
- Verdict: Phase 4 communication is stable and performant; sub-millisecond roundtrip well within hardware tolerance
- Generated plot: `is_should_plot.png` (send times vs device OK times, plus latency metrics)

### Phase 6 - Remove all legacy code paths and finalize the new architecture as the only option.
- [ ] Remove old `loop()` and `setup()` code.
- [ ] Remove old command handler registration and dispatch code.
- [ ] Remove any remaining direct transport writes from services.
- [ ] Remove any remaining library code that depends on vendor-specific APIs directly.
- [ ] Finalize documentation and add new host-side tests for diagnostics and performance.
- [ ] Remove old firmware folder if all migration targets are stable.

## Testing Strategy

- Keep using existing host `MockTransport` tests.
- Add `px_device_interfaces/tests/test_freertos_*.py` for concurrency and diagnostic behavior.
- Board-focused validation:
  - ✅ `ESP32-S3-R8`: Validated with GPIO, UART, I2C, SPI, LCD (ST7735), and OLED (SSD1306) example scripts; performance benchmarked via `plot_is_should.py` (100% packet success, sub-ms latency).
  - `ESP32-S3-R8` FastLED: Firmware build validated with `FASTLED_SUPPORT`; APA102/WS2812 hardware smoke tests completed.
  - ✅ `STM32F411`: Firmware builds successfully (5.9% flash, 11.4% RAM); GPIO smoke test passed on hardware via STLink, and host communication validated over native USB CDC (`/dev/ttyACM0`).
    - **Transport Note:** USB CDC is working and usable as the standard `GPIO_Lib` communication interface for STM32F411. No USB-to-UART bridge is required for normal host communication.
  - `Renesas RA`: Compatibility pass pending after ESP32 and STM32 are stable.

## Completed This Session

- ✅ Phase 1A: Code cleanup, stub creation, ESP32-S3-R8 board bring-up complete and validated.
- ✅ Phase 2 / 2.5: O(1) dispatch hash-table and self-registration macro system working end-to-end.
- ✅ Phase 3.1: GPIO task with timer-driven polling (10ms intervals) and ISR support, validated with 15+ seconds stable operation.
- ✅ Phase 3.2: UART task with per-instance ring buffering and all 10 command handlers, dual-instance tested and stable.
- ✅ Phase 4: All peripheral services (I2C, SPI, LCD ST7735, OLED SSD1306) ported from legacy, integrated with build flags, and validated via host example scripts.
- ✅ FastLED: APA102 and WS2812 command paths ported into the active firmware tree and validated on ESP32-S3-R8 build + hardware smoke tests.
- ✅ STM32F411 Bring-Up Phase 1A: All symbol collision/HAL clashes resolved; STM32 board profile configured with STLink upload; firmware compiles cleanly; GPIO smoke test validates on hardware (UART output).
- ✅ FastLED on STM32: Firmware builds with FastLED support enabled and hardware smoke validated over USB CDC.
- ✅ Encoder + Stepper services: Implemented new `EncoderTask` / `StepperTask` services, host APIs, and runnable examples; STM32F411 smoke tests executed over USB CDC.
- ✅ Performance baseline: 100% packet success rate, sub-millisecond latency, 0 timeouts on 202-packet test run.

## Next Priorities

1. **STM32F411 peripheral smoke tests** — Continue validating UART, I2C, SPI, LCD, OLED, FastLED, Encoder, and Stepper paths on hardware over USB CDC (`/dev/ttyACM0`).
2. **Implement proper STM32 `Wire1` support** — Add real multi-bus support for STM32 I2C in the active firmware tree, including `wire_for_id(1)`, correct `TwoWire` instance selection, and validation of OLED/I2C host scripts that currently assume `i2c_bus=1`.
3. **Arduino Uno R4 WiFi platform integration plan** — Add board profile, HAL/RTOSAL strategy, and transport/build validation needed before Matrix can be implemented.
4. **Extended reliability testing** — Multi-minute load tests, watchdog validation, queue saturation checks.
5. **Phase 6 finalization** — Remove legacy code paths and commit to FreeRTOS-based architecture as primary.

## Matrix Service Constraint

- The LED matrix service is specific to Arduino Uno R4 WiFi hardware.
- Implementing Matrix in the FreeRTOS tree requires explicit Arduino Uno R4 WiFi support first, including board profile, build path, and HAL compatibility validation.
- Matrix should therefore be treated as a follow-on task after Uno R4 integration, not as the next board-agnostic service port.

## Open Decisions

1. ✅ **Resolved:** `ESP32` reference board = `ESP32-S3-R8` (in use, validated).
2. ✅ **Resolved:** `STM32` reference board = `STM32F411` (designated; bring-up pending).
3. **Pending:** Whether `RTOSAL` v1 targets FreeRTOS only or includes a host simulation backend for unit tests.
4. **Pending:** Whether AVR stays on a frozen legacy branch or gets full RTOSAL port (recommend freeze for now).
5. **Pending:** Default memory policy during Phase 4 accumulation — mostly static allocation with pooled buffers vs. mixed heap (current: static emphasis, comfortable headroom at 10.4% RAM post-Phase 4).



