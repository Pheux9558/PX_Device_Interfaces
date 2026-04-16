#pragma once

#include "hal_types.h"

uint32_t hal_time_millis(void);
void     hal_time_delay_ms(uint32_t ms);

/* Microsecond resolution — wraps at 2^32 (~71 min). */
uint32_t hal_time_micros(void);
void     hal_time_delay_us(uint32_t us);
