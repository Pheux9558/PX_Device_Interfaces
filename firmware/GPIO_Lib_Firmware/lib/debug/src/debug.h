#pragma once
#include <stdint.h>

// Initialize debug subsystem (LED pin configuration and module flag registration)
// Should be called during setup() before main loop
void debug_init();

// Non-blocking heartbeat function to be called every loop iteration
// Only active when DEBUG build flag is set
// Uses internal timing to control LED toggle rate
void debug_heartbeat();

// Return debug module flag string (for build flags aggregation)
const char *debug_module_flags();
