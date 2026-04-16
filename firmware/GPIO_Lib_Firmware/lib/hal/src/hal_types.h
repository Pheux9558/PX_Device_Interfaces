#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    HAL_STATUS_OK = 0,
    HAL_STATUS_ERROR,
    HAL_STATUS_TIMEOUT,
    HAL_STATUS_UNSUPPORTED,
    HAL_STATUS_BUSY,
} hal_status_t;
