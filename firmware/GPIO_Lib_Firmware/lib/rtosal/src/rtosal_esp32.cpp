#include "rtosal.h"

#if defined(ESP32)

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <freertos/task.h>

/*
 * ESP32-specific RTOS port hooks.
 * Phase-1 keeps this as a placeholder so service code can start integrating
 * against RTOSAL without directly including ESP-IDF/FreeRTOS headers yet.
 */

extern "C" const char *rtosal_port_name_esp32(void) {
    return "esp32";
}

static TickType_t timeout_to_ticks(uint32_t timeout_ms) {
    if (timeout_ms == 0) {
        return 0;
    }
    if (timeout_ms == UINT32_MAX) {
        return portMAX_DELAY;
    }
    return pdMS_TO_TICKS(timeout_ms);
}

extern "C" rtosal_status_t rtosal_init(void) {
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_task_create(const rtosal_task_config_t *cfg, rtosal_task_t *out_task) {
    if (!cfg || !cfg->fn) {
        if (out_task) *out_task = NULL;
        return RTOSAL_ERROR;
    }
    TaskHandle_t handle = NULL;
    // ESP-IDF expects stack depth in bytes. Our RTOSAL config uses words.
    uint32_t stack_bytes = (uint32_t)cfg->stack_words * (uint32_t)sizeof(StackType_t);
    BaseType_t ok = xTaskCreate(
        cfg->fn,
        cfg->name ? cfg->name : "rtosal",
        (configSTACK_DEPTH_TYPE)stack_bytes,
        cfg->arg,
        (UBaseType_t)cfg->priority,
        &handle);
    if (out_task) {
        *out_task = (rtosal_task_t)handle;
    }
    return ok == pdPASS ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_task_delete(rtosal_task_t task) {
    vTaskDelete((TaskHandle_t)task);
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_queue_create(const rtosal_queue_config_t *cfg, rtosal_queue_t *out_queue) {
    if (!cfg || cfg->depth == 0 || cfg->item_size == 0) {
        if (out_queue) *out_queue = NULL;
        return RTOSAL_ERROR;
    }
    QueueHandle_t q = xQueueCreate((UBaseType_t)cfg->depth, (UBaseType_t)cfg->item_size);
    if (out_queue) {
        *out_queue = (rtosal_queue_t)q;
    }
    return q ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_queue_delete(rtosal_queue_t q) {
    if (!q) return RTOSAL_ERROR;
    vQueueDelete((QueueHandle_t)q);
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_queue_send(rtosal_queue_t q, const void *item, uint32_t timeout_ms) {
    if (!q || !item) return RTOSAL_ERROR;
    BaseType_t ok = xQueueSend((QueueHandle_t)q, item, timeout_to_ticks(timeout_ms));
    if (ok == pdPASS) return RTOSAL_OK;
    return timeout_ms == 0 ? RTOSAL_FULL : RTOSAL_TIMEOUT;
}

extern "C" rtosal_status_t rtosal_queue_receive(rtosal_queue_t q, void *item, uint32_t timeout_ms) {
    if (!q || !item) return RTOSAL_ERROR;
    BaseType_t ok = xQueueReceive((QueueHandle_t)q, item, timeout_to_ticks(timeout_ms));
    if (ok == pdPASS) return RTOSAL_OK;
    return timeout_ms == 0 ? RTOSAL_EMPTY : RTOSAL_TIMEOUT;
}

extern "C" rtosal_status_t rtosal_mutex_create(rtosal_mutex_t *out_mutex) {
    if (!out_mutex) return RTOSAL_ERROR;
    SemaphoreHandle_t m = xSemaphoreCreateMutex();
    *out_mutex = (rtosal_mutex_t)m;
    return m ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_mutex_lock(rtosal_mutex_t m, uint32_t timeout_ms) {
    if (!m) return RTOSAL_ERROR;
    BaseType_t ok = xSemaphoreTake((SemaphoreHandle_t)m, timeout_to_ticks(timeout_ms));
    if (ok == pdTRUE) return RTOSAL_OK;
    return timeout_ms == 0 ? RTOSAL_FULL : RTOSAL_TIMEOUT;
}

extern "C" rtosal_status_t rtosal_mutex_unlock(rtosal_mutex_t m) {
    if (!m) return RTOSAL_ERROR;
    BaseType_t ok = xSemaphoreGive((SemaphoreHandle_t)m);
    return ok == pdTRUE ? RTOSAL_OK : RTOSAL_ERROR;
}

extern "C" rtosal_status_t rtosal_notify_give(rtosal_task_t task) {
    if (!task) return RTOSAL_ERROR;
    xTaskNotifyGive((TaskHandle_t)task);
    return RTOSAL_OK;
}

extern "C" rtosal_status_t rtosal_notify_take(uint32_t timeout_ms, uint32_t *out_value) {
    uint32_t v = ulTaskNotifyTake(pdTRUE, timeout_to_ticks(timeout_ms));
    if (out_value) *out_value = v;
    if (v > 0) return RTOSAL_OK;
    return timeout_ms == 0 ? RTOSAL_EMPTY : RTOSAL_TIMEOUT;
}

extern "C" void rtosal_delay_ms(uint32_t delay_ms) {
    vTaskDelay(timeout_to_ticks(delay_ms));
}

extern "C" void rtosal_delay_until(rtosal_tick_t *last_wake_tick, rtosal_tick_t period_ms) {
    if (!last_wake_tick) return;
    TickType_t last = (TickType_t)(*last_wake_tick);
    xTaskDelayUntil(&last, pdMS_TO_TICKS(period_ms));
    *last_wake_tick = (rtosal_tick_t)last;
}

extern "C" rtosal_tick_t rtosal_now_ticks(void) {
    return (rtosal_tick_t)xTaskGetTickCount();
}

#endif
