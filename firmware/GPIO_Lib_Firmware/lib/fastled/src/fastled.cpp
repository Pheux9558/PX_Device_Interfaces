#include "fastled.h"
#include "cmd.h"
#include "modules.h"
#include "serial.h"
#if defined(ARDUINO)
#include <Arduino.h>
#else
#include <string.h>
#include <stdio.h>
#endif
#include <stdlib.h>

// Simple FastLED support implementation with APA102 (bit-banged SPI).
// Supports multiple instances identified by a 16-bit identifier.

#define MAX_FASTLED_INSTANCES 4

struct fastled_instance_t {
    uint16_t id;
    uint16_t data_pin;
    uint16_t clock_pin;
    uint8_t  type; // FASTLED_TYPE_*
    uint16_t num_leds;
    uint8_t *buf; // RGB bytes (num_leds * 3)
    uint8_t brightness; // 0-255 brightness (host scale)
    bool used;
};

static struct fastled_instance_t g_instances[MAX_FASTLED_INSTANCES];

static struct fastled_instance_t *find_instance(uint16_t id) {
    for (int i = 0; i < MAX_FASTLED_INSTANCES; ++i) if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    return NULL;
}

static struct fastled_instance_t *alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_FASTLED_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].data_pin = 0xFFFF;
            g_instances[i].clock_pin = 0xFFFF;
            g_instances[i].type = FASTLED_TYPE_APA102;
            g_instances[i].num_leds = 0;
            g_instances[i].buf = NULL;
            g_instances[i].brightness = 0xFF;
            return &g_instances[i];
        }
    }
    return NULL;
}

static void free_instance(struct fastled_instance_t *inst) {
    if (!inst) return;
    if (inst->buf) {
        free(inst->buf);
        inst->buf = NULL;
    }
    inst->used = false;
}

void fastled_init() {
    for (int i = 0; i < MAX_FASTLED_INSTANCES; ++i) {
        g_instances[i].used = false;
        g_instances[i].buf = NULL;
    }
    modules_add_flag(fastled_module_flags());
}

const char *fastled_module_flags() {
    return "FASTLED";
}

#if defined(ARDUINO)
// Bit-banged APA102 send (MSB first for each byte). Assumes buf is RGB bytes per LED.
// `brightness` is host-scale 0-255 and will be mapped to APA102 5-bit value.
static void apa102_send(uint16_t data_pin, uint16_t clock_pin, const uint8_t *buf, uint16_t num_leds, uint8_t brightness) {
    if (data_pin == 0xFFFF || clock_pin == 0xFFFF) return;
    pinMode((int)data_pin, OUTPUT);
    pinMode((int)clock_pin, OUTPUT);
    digitalWrite((int)clock_pin, LOW);

    // Start frame: 32 zeros
    for (int i = 0; i < 4; ++i) {
        for (int b = 7; b >= 0; --b) {
            digitalWrite((int)data_pin, LOW);
            digitalWrite((int)clock_pin, HIGH);
            digitalWrite((int)clock_pin, LOW);
        }
    }

    // LED frames
    for (uint16_t i = 0; i < num_leds; ++i) {
        uint8_t r = buf[i*3 + 0];
        uint8_t g = buf[i*3 + 1];
        uint8_t b = buf[i*3 + 2];
        // global brightness: APA102 stores 5 bits (0-31) in lower bits, top three bits must be '111'
        uint8_t gb5 = (uint8_t)(brightness >> 3); // 0..31
        uint8_t gb = 0xE0 | (gb5 & 0x1F);
        uint8_t frame[4] = { gb, b, g, r };
        for (int j = 0; j < 4; ++j) {
            for (int bit = 7; bit >= 0; --bit) {
                digitalWrite((int)data_pin, (frame[j] >> bit) & 1);
                digitalWrite((int)clock_pin, HIGH);
                digitalWrite((int)clock_pin, LOW);
            }
        }
    }

    // End frame: at least (num_leds+15)/16 bits of 1; easiest: send 4 bytes of 0xFF
    for (int i = 0; i < 4; ++i) {
        for (int b = 7; b >= 0; --b) {
            digitalWrite((int)data_pin, HIGH);
            digitalWrite((int)clock_pin, HIGH);
            digitalWrite((int)clock_pin, LOW);
        }
    }
}
#endif

bool fastled_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0110: // CMD_FASTLED_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0111: // CMD_FASTLED_SET_DATA_PIN
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (uint16_t)payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->data_pin = pin;
                cmd_send_ok();
            }
            return true;
        case 0x0112: // CMD_FASTLED_SET_CLOCK_PIN
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (uint16_t)payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->clock_pin = pin;
                cmd_send_ok();
            }
            return true;
        case 0x0113: // CMD_FASTLED_SET_LED_TYPE
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t type = payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->type = type;
                cmd_send_ok();
            }
            return true;
        case 0x0114: // CMD_FASTLED_SET_NUM_LEDS
            if (len < 4) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t num = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (inst->buf) { free(inst->buf); inst->buf = NULL; }
                if (num > 0) {
                    inst->buf = (uint8_t*)malloc((size_t)num * 3);
                    if (!inst->buf) { inst->num_leds = 0; cmd_send_error(); return true; }
                    memset(inst->buf, 0, (size_t)num * 3);
                }
                inst->num_leds = num;
                cmd_send_ok();
            }
            return true;
        case 0x0115: // CMD_FASTLED_SHOW
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                const uint8_t *data = &payload[2];
                uint16_t data_len = (uint16_t)(len - 2);
                uint16_t expected = (uint16_t)(inst->num_leds * 3);
                if (data_len < expected) {
                    // partial updates allowed: copy min
                    uint16_t to_copy = data_len < expected ? data_len : expected;
                    if (inst->buf && to_copy) memcpy(inst->buf, data, to_copy);
                } else {
                    if (inst->buf && expected) memcpy(inst->buf, data, expected);
                }

#if defined(ARDUINO)
                if (inst->type == FASTLED_TYPE_APA102) {
                    apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
                } else {
                    // WS2812 or other types not implemented yet
                }
#endif
                cmd_send_ok();
            }
            return true;
        case 0x0116: // CMD_FASTLED_SET_BRIGHTNESS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t brightness = payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->brightness = brightness;
                cmd_send_ok();
            }
            return true;
        default:
            return false;
    }
}
