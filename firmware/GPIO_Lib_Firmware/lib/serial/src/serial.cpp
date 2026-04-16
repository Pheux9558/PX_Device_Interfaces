// Basic serial wrapper that maps to Arduino Serial when building for Arduino
#include "serial.h"

#if defined(ARDUINO)
#include <Arduino.h>

#if defined(ARDUINO_ARCH_STM32) && defined(PIO_FRAMEWORK_ARDUINO_ENABLE_CDC)
#if defined(SERIAL_PORT_USBVIRTUAL)
#define GPIOLIB_TRANSPORT_SERIAL SERIAL_PORT_USBVIRTUAL
#else
#define GPIOLIB_TRANSPORT_SERIAL Serial
#endif
#else
#define GPIOLIB_TRANSPORT_SERIAL Serial
#endif

void serial_begin(unsigned long baud) {
    GPIOLIB_TRANSPORT_SERIAL.begin(baud);
    // Note: On Renesas/SAMD CDC devices, Serial.begin() doesn't wait for enumeration.
    // The device will send data but the host may not receive it until the port is opened.
    // This is normal CDC behavior. The application code (main.cpp) will send GPIO_READY
    // after a brief delay to allow enumeration.
}
int serial_available() { return GPIOLIB_TRANSPORT_SERIAL.available(); }
int serial_read() { return GPIOLIB_TRANSPORT_SERIAL.read(); }
size_t serial_write(const uint8_t *buf, size_t len) { 
    #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD)
    // USB CDC on Renesas/SAMD requires explicit readiness checks
    // The device may not be enumerated yet, so check if port is open
    if (!GPIOLIB_TRANSPORT_SERIAL) return 0;  // Port not open yet, drop data
    #endif
    
    size_t written = GPIOLIB_TRANSPORT_SERIAL.write(buf, len); 
    
    #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_ARCH_STM32)
    // Flush immediately after every write to ensure USB CDC sends the data.
    // On STM32duino the TX FIFO is 64 bytes; without flush a multi-packet response
    // (>64 bytes total in a burst) can be split and the tail never sent until the
    // next delay(), causing _await_response() timeouts on the host side.
    GPIOLIB_TRANSPORT_SERIAL.flush();
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
