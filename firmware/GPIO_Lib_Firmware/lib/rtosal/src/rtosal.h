#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void *rtosal_task_t;
typedef void *rtosal_queue_t;
typedef void *rtosal_mutex_t;
typedef uint32_t rtosal_tick_t;

// Sentinel timeout meaning "wait forever" for rtosal_mutex_lock / rtosal_queue_* calls.
#define RTOSAL_MAX_DELAY  0xFFFFFFFFU

typedef enum {
    RTOSAL_OK = 0,
    RTOSAL_TIMEOUT,
    RTOSAL_FULL,
    RTOSAL_EMPTY,
    RTOSAL_ERROR,
} rtosal_status_t;

typedef void (*rtosal_task_fn_t)(void *arg);

typedef struct {
    const char *name;
    rtosal_task_fn_t fn;
    void *arg;
    uint16_t stack_words;
    uint8_t priority;
} rtosal_task_config_t;

typedef struct {
    uint16_t depth;
    uint16_t item_size;
} rtosal_queue_config_t;

rtosal_status_t rtosal_init(void);
rtosal_status_t rtosal_task_create(const rtosal_task_config_t *cfg, rtosal_task_t *out_task);
rtosal_status_t rtosal_task_delete(rtosal_task_t task);
rtosal_status_t rtosal_queue_create(const rtosal_queue_config_t *cfg, rtosal_queue_t *out_queue);
rtosal_status_t rtosal_queue_delete(rtosal_queue_t q);
rtosal_status_t rtosal_queue_send(rtosal_queue_t q, const void *item, uint32_t timeout_ms);
rtosal_status_t rtosal_queue_receive(rtosal_queue_t q, void *item, uint32_t timeout_ms);
rtosal_status_t rtosal_mutex_create(rtosal_mutex_t *out_mutex);
rtosal_status_t rtosal_mutex_lock(rtosal_mutex_t m, uint32_t timeout_ms);
rtosal_status_t rtosal_mutex_unlock(rtosal_mutex_t m);
rtosal_status_t rtosal_notify_give(rtosal_task_t task);
rtosal_status_t rtosal_notify_take(uint32_t timeout_ms, uint32_t *out_value);
void rtosal_delay_ms(uint32_t delay_ms);
void rtosal_delay_until(rtosal_tick_t *last_wake_tick, rtosal_tick_t period_ms);
rtosal_tick_t rtosal_now_ticks(void);

#ifdef __cplusplus
}
#endif
