#include "rtosal.h"

#if defined(STM32F1) || defined(STM32F4) || defined(ARDUINO_ARCH_STM32)

#include <Arduino.h>

/*
 * STM32 bare-metal RTOSAL port.
 *
 * STM32 + Arduino framework runs single-threaded in loop() — there is no
 * FreeRTOS scheduler available through PlatformIO arduino-stm32 unless an
 * external RTOS library is added. Until then this port provides:
 *   - No-op task creation (returns RTOSAL_ERROR so callers fall back to poll)
 *   - Always-succeeding mutex (single-threaded: no real contention possible)
 *   - millis()-based tick counter
 */

// Sentinel value stored in out_mutex to represent a "live" mutex handle
// without any OS backing. Must be non-NULL so callers don't treat it as
// uninitialized.
#define RTOSAL_STM32_MUTEX_SENTINEL  ((void *)(uintptr_t)0xBEEFU)

extern "C" rtosal_status_t rtosal_init(void) {
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_task_create(const rtosal_task_config_t *cfg, rtosal_task_t *out_task) {
    /* No FreeRTOS available — callers must fall back to stepper_poll() */
    (void)cfg;
    if (out_task) *out_task = NULL;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_task_delete(rtosal_task_t task) {
    (void)task;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_queue_create(const rtosal_queue_config_t *cfg, rtosal_queue_t *out_queue) {
    (void)cfg;
    if (out_queue) *out_queue = NULL;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_queue_delete(rtosal_queue_t q) {
    (void)q;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_queue_send(rtosal_queue_t q, const void *item, uint32_t timeout_ms) {
    (void)q; (void)item; (void)timeout_ms;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_queue_receive(rtosal_queue_t q, void *item, uint32_t timeout_ms) {
    (void)q; (void)item; (void)timeout_ms;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_mutex_create(rtosal_mutex_t *out_mutex) {
    /* Single-threaded: just hand back a non-NULL sentinel */
    if (!out_mutex) return RTOSAL_ERROR;
    *out_mutex = RTOSAL_STM32_MUTEX_SENTINEL;
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_mutex_lock(rtosal_mutex_t m, uint32_t timeout_ms) {
    /* Single-threaded: mutex is always immediately available */
    (void)timeout_ms;
    return m ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_mutex_unlock(rtosal_mutex_t m) {
    return m ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_notify_give(rtosal_task_t task) {
    (void)task;
    return RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_notify_take(uint32_t timeout_ms, uint32_t *out_value) {
    (void)timeout_ms;
    if (out_value) *out_value = 0;
    return RTOSAL_ERROR;
}

extern "C" void rtosal_delay_ms(uint32_t delay_ms) {
    delay(delay_ms);
}

extern "C" void rtosal_delay_until(rtosal_tick_t *last_wake_tick, rtosal_tick_t period_ms) {
    if (!last_wake_tick) return;
    rtosal_tick_t now = (rtosal_tick_t)millis();
    rtosal_tick_t elapsed = now - *last_wake_tick;
    if (elapsed < period_ms) {
        delay(period_ms - elapsed);
    }
    *last_wake_tick = (rtosal_tick_t)millis();
}

extern "C" rtosal_tick_t rtosal_now_ticks(void) {
    return (rtosal_tick_t)millis();
}

#endif
