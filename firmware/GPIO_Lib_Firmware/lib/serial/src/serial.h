// Serial HAL abstraction header
#pragma once

#include <stdint.h>
#include <stddef.h>

void serial_begin(unsigned long baud);
int serial_available();
int serial_read();
size_t serial_write(const uint8_t *buf, size_t len);
