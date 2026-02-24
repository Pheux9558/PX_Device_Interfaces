// Basic serial wrapper that maps to Arduino Serial when building for Arduino
#include "serial.h"

#if defined(ARDUINO)
#include <Arduino.h>

void serial_begin(unsigned long baud) {
    Serial.begin(baud);
    // Note: On Renesas/SAMD CDC devices, Serial.begin() doesn't wait for enumeration.
    // The device will send data but the host may not receive it until the port is opened.
    // This is normal CDC behavior. The application code (main.cpp) will send GPIO_READY
    // after a brief delay to allow enumeration.
}
int serial_available() { return Serial.available(); }
int serial_read() { return Serial.read(); }
size_t serial_write(const uint8_t *buf, size_t len) { 
    #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD)
    // USB CDC on Renesas and SAMD requires explicit flush and waiting for readiness
    // The device may not be enumerated yet, so check if port is open
    if (!Serial) return 0;  // Port not open yet, drop data
    #endif
    
    size_t written = Serial.write(buf, len); 
    
    #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD)
    // Flush immediately after every write to ensure USB CDC sends the data
    Serial.flush();
    #endif
    
    return written;
}

#else
// Fallback stubs for non-Arduino builds (useful for unit testing on host)
#include <stdio.h>
#include <string.h>

void serial_begin(unsigned long baud) { (void)baud; }
int serial_available() { return 0; }
int serial_read() { return -1; }
size_t serial_write(const uint8_t *buf, size_t len) { return fwrite(buf, 1, len, stdout); }

#endif
