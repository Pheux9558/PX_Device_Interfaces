#pragma once
#include <stdint.h>

// Initialize board module (registers build flags)
void board_init();

// Return board flag string (statically allocated)
const char *board_module_flags();
