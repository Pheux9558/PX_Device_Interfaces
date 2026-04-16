#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void encoder_init(void);
void encoder_poll(void);
bool encoder_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *encoder_module_flags(void);

/**
 * Read a thread-safe snapshot of an encoder's position and direction.
 * Returns true if the encoder exists and is active, false otherwise.
 * out_* pointers may be NULL if that field is not needed.
 */
bool encoder_get_snapshot(uint16_t enc_id,
                          int32_t *out_position,
                          int32_t *out_revolutions,
                          int8_t  *out_direction);

#ifdef __cplusplus
}
#endif
