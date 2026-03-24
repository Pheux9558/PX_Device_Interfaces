# FreeRTOS Rework - Architecture and Portability Plan

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
- ESP32 DevKit / ESP32 Pico / ESP32-S3 T-Dongle.
- STM32 Nucleo / BlackPill-class boards with enough RAM for queues and multiple tasks.

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
- [ ] Add `RTOSAL` skeleton and define the common API.
- [ ] Add `HAL` skeleton for GPIO/UART/I2C/SPI/time.
- [ ] Add first-class ESP32 and STM32 build targets.
- [ ] Implement `serial_rtos.c/h` with `RxTask`, `TxTask`, `response_queue`, and `tx_mutex`.
- [ ] Replace direct `serial_write()` response generation with queued TX.
- [ ] Remove `calc_delay()` and global idle delays from the main execution path.

### Phase 1A - Board bring-up matrix
- [ ] Bring up ESP32 reference board first.
- [ ] Bring up STM32 reference board second.
- [ ] Keep Renesas compiling through a compatibility port.
- [ ] Decide whether AVR remains a frozen legacy branch.

### Phase 2 - Dispatch redesign
- [ ] Implement `cmd_dispatch.c/h` with hash-table lookup.
- [ ] Replace range-scan handler registration.
- [ ] Add self-registration macros for service commands.
- [ ] Migrate GPIO and UART first.

### Phase 3 - Service tasks
- [ ] Implement `GpioTask` with timer-driven polling using `rtosal_delay_until()`.
- [ ] Implement `UartTask` with per-instance protection and optional RX buffering.
- [ ] Move service state ownership into the owning task.
- [ ] Move vendor-specific code fully behind HAL ports.

### Phase 4 - Remaining services
- [ ] I2C service task.
- [ ] SPI service task.
- [ ] Display and LED tasks.
- [ ] Lower-priority compatibility services such as encoder and matrix.

### Phase 5 - Reliability and performance
- [ ] Add `SysMonTask`.
- [ ] Add pool allocator and queue depth instrumentation.
- [ ] Add service restart policy where safe.
- [ ] Benchmark throughput and latency on ESP32 and STM32.

## Testing Strategy

- Keep using existing host `MockTransport` tests.
- Add `px_device_interfaces/tests/test_freertos_*.py` for concurrency and diagnostic behavior.
- Add board-focused validation:
  - `ESP32`: UART duplex throughput, ISR wake latency, queue saturation.
  - `STM32`: GPIO timing jitter, UART latency, DMA/interrupt receive behavior.
  - `Renesas`: compatibility regression after the first two are stable.

## Open Decisions

1. Choose the first ESP32 reference board for optimization work.
2. Choose the first STM32 reference board for portability work.
3. Decide whether `RTOSAL` v1 targets FreeRTOS only or includes a host simulation backend immediately.
4. Decide whether AVR stays on a frozen legacy branch.
5. Decide the default memory policy: mostly static plus pooled buffers, or mixed with `heap_4`.

