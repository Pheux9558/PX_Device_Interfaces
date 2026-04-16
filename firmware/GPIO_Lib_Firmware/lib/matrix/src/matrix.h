// UNO R4 Matrix RTOS Service - Phase 4 Implementation Placeholder
// Legacy implementation moved to lib/_legacy/matrix for reference
#pragma once

#include <stdint.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

void matrix_init(void);
int matrix_update(void);
	bool matrix_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

#ifdef __cplusplus
}
#endif
