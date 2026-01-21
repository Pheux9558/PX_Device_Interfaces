// Basic serial wrapper that maps to Arduino Serial when building for Arduino
#include "serial.h"

#if defined(ARDUINO)
#include <Arduino.h>

void serial_begin(unsigned long baud) { Serial.begin(baud); }
int serial_available() { return Serial.available(); }
int serial_read() { return Serial.read(); }
size_t serial_write(const uint8_t *buf, size_t len) { return Serial.write(buf, len); }

#else
// Fallback stubs for non-Arduino builds (useful for unit testing on host)
#include <stdio.h>
#include <string.h>

void serial_begin(unsigned long baud) { (void)baud; }
int serial_available() { return 0; }
int serial_read() { return -1; }
size_t serial_write(const uint8_t *buf, size_t len) { return fwrite(buf, 1, len, stdout); }

#endif
