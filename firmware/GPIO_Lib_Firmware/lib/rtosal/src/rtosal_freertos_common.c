#include "rtosal.h"

/*
 * Phase-1 scaffold.
 *
 * This file intentionally provides no-op/error-first stubs so we can
 * compile while wiring architecture. Board-specific FreeRTOS bindings are
 * implemented in per-target files as we migrate services.
 */

/* ESP32 uses rtosal_esp32.cpp; STM32 uses rtosal_stm32.cpp.
 * This file provides no-op stubs only for targets not covered above. */
#if !defined(ESP32) && !defined(ARDUINO_ARCH_STM32) && !defined(STM32F4) && !defined(STM32F1)

rtosal_status_t rtosal_init(void) {
    return RTOSAL_OK;
}

rtosal_status_t rtosal_task_create(const rtosal_task_config_t *cfg, rtosal_task_t *out_task) {
    (void)cfg;
    if (out_task) *out_task = 0;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_task_delete(rtosal_task_t task) {
    (void)task;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_queue_create(const rtosal_queue_config_t *cfg, rtosal_queue_t *out_queue) {
    (void)cfg;
    if (out_queue) *out_queue = 0;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_queue_delete(rtosal_queue_t q) {
    (void)q;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_queue_send(rtosal_queue_t q, const void *item, uint32_t timeout_ms) {
    (void)q;
    (void)item;
    (void)timeout_ms;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_queue_receive(rtosal_queue_t q, void *item, uint32_t timeout_ms) {
    (void)q;
    (void)item;
    (void)timeout_ms;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_mutex_create(rtosal_mutex_t *out_mutex) {
    if (out_mutex) *out_mutex = 0;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_mutex_lock(rtosal_mutex_t m, uint32_t timeout_ms) {
    (void)m;
    (void)timeout_ms;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_mutex_unlock(rtosal_mutex_t m) {
    (void)m;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_notify_give(rtosal_task_t task) {
    (void)task;
    return RTOSAL_ERROR;
}

rtosal_status_t rtosal_notify_take(uint32_t timeout_ms, uint32_t *out_value) {
    (void)timeout_ms;
    if (out_value) *out_value = 0;
    return RTOSAL_ERROR;
}

void rtosal_delay_ms(uint32_t delay_ms) {
    (void)delay_ms;
}

void rtosal_delay_until(rtosal_tick_t *last_wake_tick, rtosal_tick_t period_ms) {
    (void)last_wake_tick;
    (void)period_ms;
}

rtosal_tick_t rtosal_now_ticks(void) {
    return 0;
}

#endif
