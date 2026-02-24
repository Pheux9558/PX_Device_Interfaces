#include "firmware.h"
#include "cmd.h"
#include "gpio.h"
#include "modules.h"
#include <string.h>
#include <stdio.h>

#if defined(ARDUINO)
#include <Arduino.h>
    #if defined(ARDUINO_ARCH_ESP32)
    #include <esp_system.h>
    #endif
    #if defined(ARDUINO_ARCH_AVR)
    #include <avr/wdt.h>
    #endif
#endif

// construct firmware name from BOARD and optional custom name
// format: "GPIO_Lib_Firmware_<BOARD>" with an optional
// "_<CUSTOM_NAME>" suffix.

// helpers to stringify a macro value
#define _STR1(x) #x
#define _STR(x) _STR1(x)

#ifndef GPIO_LIB_FIRMWARE_NAME
    #ifdef BOARD
        #define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_" _STR(BOARD)
    #else
        #define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_Generic"
    #endif
#endif

#ifdef GPIO_LIB_FIRMWARE_CUSTOM_NAME
    /* append custom name if provided.  This redefines the base name but
       keeps the BOARD portion intact (or Generic when BOARD missing). */
    #undef GPIO_LIB_FIRMWARE_NAME
    #ifdef BOARD
        #define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_" _STR(BOARD) "_" GPIO_LIB_FIRMWARE_CUSTOM_NAME
    #else
        #define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_Generic_" GPIO_LIB_FIRMWARE_CUSTOM_NAME
    #endif
#endif

static const char *s_firmware_name = GPIO_LIB_FIRMWARE_NAME;
static const uint8_t s_fw_major = 1;
static const uint8_t s_fw_minor = 0;
static const uint8_t s_fw_patch = 0;

bool firmware_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    (void)payload; (void)len;
    switch (cmd) {
        case 0xFFFE: // CMD_FIRMWARE_INFO
            cmd_send_response(0xFFFE, (const uint8_t *)s_firmware_name, (uint16_t)strlen(s_firmware_name));
            cmd_send_ok();
            return true;
        case 0xFFFF: // CMD_FIRMWARE_VERSION
        {
            uint8_t v[3] = { s_fw_major, s_fw_minor, s_fw_patch };
            cmd_send_response(0xFFFF, v, 3);
            cmd_send_ok();
            return true;
        }
        case 0xFFFC: // CMD_FIRMWARE_RESET
        {
            #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_ARCH_STM32)
            cmd_send_ok();
            delay(10);
            NVIC_SystemReset();
            #elif defined(ARDUINO_ARCH_ESP32)
            cmd_send_ok();
            delay(10);
            ESP.restart();
            #elif defined(ARDUINO_ARCH_AVR)
            cmd_send_ok();
            wdt_enable(WDTO_15MS);
            while (1) { }
            #else
            cmd_send_error();
            #endif
            return true;
        }
        case 0xFFFD: // CMD_FIRMWARE_BUILD_FLAGS
        {
            char buf[256];
            // gather flags registered by modules
            uint16_t n = modules_get_flags(buf, sizeof(buf));
            if (n == 0) {
                cmd_send_error();
            } else {
                // sanitize flags: replace unsafe chars and collapse whitespace
                // allow alnum and these chars: - _ = . / +
                char out[256];
                uint16_t op = 0;
                bool last_space = false;
                for (uint16_t i = 0; i < n && op + 1 < sizeof(out); ++i) {
                    unsigned char ch = (unsigned char)buf[i];
                    bool ok = false;
                    if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9')) ok = true;
                    if (ch == '-' || ch == '_' || ch == '=' || ch == '.' || ch == '/' || ch == '+') ok = true;
                    if (ok) {
                        out[op++] = (char)ch;
                        last_space = false;
                    } else {
                        // treat as separator
                        if (!last_space) {
                            out[op++] = ' ';
                            last_space = true;
                        }
                    }
                }
                // trim trailing space
                while (op > 0 && out[op-1] == ' ') op--;
                if (op < sizeof(out)) out[op] = '\0';
                cmd_send_response(0xFFFD, (const uint8_t *)out, op);
                cmd_send_ok();
            }
            return true;
        }
        default:
            return false;
    }
}
