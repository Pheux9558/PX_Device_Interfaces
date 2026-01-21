#pragma once
#include <stdint.h>

// Register a short module flag string. The string is copied internally.
// Returns true on success (registered), false if registry full.
bool modules_add_flag(const char *flag);

// Fill `buf` with concatenated flags separated by ';'. Returns number of bytes written (excluding NUL).
uint16_t modules_get_flags(char *buf, uint16_t bufsize);

// Initialize modules registry (safe to call multiple times)
void modules_init();
