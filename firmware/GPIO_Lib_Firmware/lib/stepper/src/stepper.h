#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void stepper_init(void);
void stepper_poll(void);
bool stepper_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *stepper_module_flags(void);

#ifdef __cplusplus
}
#endif
