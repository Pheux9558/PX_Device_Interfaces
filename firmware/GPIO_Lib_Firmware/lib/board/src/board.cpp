#include "board.h"
#include "modules.h"
#include <stdio.h>
#include <string.h>

// Compose board and MCU identifiers based on compile-time macros.
// Produces small, safe tokens for build-flags like "BOARD=esp32" and "MCU=esp32-pico-d4".
const char *board_module_flags() {
    static char buf[128];
    buf[0] = '\0';

    // Prioritize very specific board/MCU macros first
#if defined(ESP32_PICO_D4)
    snprintf(buf, sizeof(buf), "BOARD=esp32 MCU=esp32-pico-d4");
#elif defined(ESP32)
    snprintf(buf, sizeof(buf), "BOARD=esp32 MCU=esp32");
#elif defined(ESP8266)
    snprintf(buf, sizeof(buf), "BOARD=esp8266 MCU=esp8266");
#elif defined(ARDUINO_AVR_MEGA2560) || defined(__AVR_ATmega2560__)
    snprintf(buf, sizeof(buf), "BOARD=arduino_mega MCU=atmega2560");
#elif defined(ARDUINO_AVR_UNO) || defined(__AVR_ATmega328P__)
    snprintf(buf, sizeof(buf), "BOARD=arduino_uno MCU=atmega328p");
#elif defined(ARDUINO_ARCH_RP2040) || defined(PICO_RP2040) || defined(RP2040)
    snprintf(buf, sizeof(buf), "BOARD=rp2040 MCU=rp2040");
#elif defined(NRF52_SERIES) || defined(NRF52832_XXAA) || defined(NRF52840_XXAA) || defined(NRF52832)
    snprintf(buf, sizeof(buf), "BOARD=nrf52 MCU=nrf52");
#elif defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_SAMD_ZERO)
    snprintf(buf, sizeof(buf), "BOARD=samd MCU=samd21");
#elif defined(__SAMD51__)
    snprintf(buf, sizeof(buf), "BOARD=samd MCU=samd51");
#elif defined(__IMXRT1062__)
    snprintf(buf, sizeof(buf), "BOARD=teensy4 MCU=imxrt1062");
#elif defined(__MK20DX256__)
    snprintf(buf, sizeof(buf), "BOARD=teensy3 MCU=mkl2x");
#elif defined(STM32F4) || defined(STM32F4xx) || defined(__STM32F4xx)
    snprintf(buf, sizeof(buf), "BOARD=stm32 MCU=stm32f4");
#elif defined(STM32F1) || defined(__STM32F1__)
    snprintf(buf, sizeof(buf), "BOARD=stm32 MCU=stm32f1");
#elif defined(__arm__) && defined(ARDUINO_ARCH_MBOSS)
    snprintf(buf, sizeof(buf), "BOARD=arm_generic MCU=arm");
#elif defined(__AVR__)
    snprintf(buf, sizeof(buf), "BOARD=avr_generic MCU=avr");
#else
    snprintf(buf, sizeof(buf), "BOARD=generic MCU=generic");
#endif

    return buf;
}

void board_init() {
    // Register board and MCU flags as a single token string (modules expects short strings)
    const char *s = board_module_flags();
    if (s && s[0]) {
        // split tokens on space and register each separately for clarity
        // simplest approach: register the full string and also split components
        modules_add_flag(s);
        // register individual tokens if present
        // find first space
        const char *p = s;
        while (*p) {
            // find next space
            const char *sp = p;
            while (*sp && *sp != ' ') sp++;
            // copy token
            char tok[64];
            int len = (int)(sp - p);
            if (len > 0 && len < (int)sizeof(tok)) {
                memcpy(tok, p, (size_t)len);
                tok[len] = '\0';
                modules_add_flag(tok);
            }
            if (!*sp) break;
            p = sp + 1;
        }
    }
}
