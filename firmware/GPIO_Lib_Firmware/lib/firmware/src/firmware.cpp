#include "firmware.h"
#include "cmd.h"
#include "gpio.h"
#include "modules.h"
#include <string.h>
#include <stdio.h>

#ifdef ARDUINO_UNO
  // specific includes or definitions for Arduino Uno can go here
  # define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_Arduino_Uno"
#elif defined(ESP32_PICO_D4)
  // specific includes or definitions for ESP32 Pico D4 can go here
  # define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_ESP32_Pico_D4"
#else
  // default includes or definitions
  # define GPIO_LIB_FIRMWARE_NAME "GPIO_Lib_Firmware_Generic"
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
            return true;
        case 0xFFFF: // CMD_FIRMWARE_VERSION
        {
            uint8_t v[3] = { s_fw_major, s_fw_minor, s_fw_patch };
            cmd_send_response(0xFFFF, v, 3);
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
            }
            return true;
        }
        default:
            return false;
    }
}

const char *firmware_module_flags() {
    return "FIRMWARE=1.0";
}
