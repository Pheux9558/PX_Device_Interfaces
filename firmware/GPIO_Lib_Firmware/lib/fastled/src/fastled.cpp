#include "fastled.h"
#include "cmd.h"
#include "modules.h"
#include "serial.h"
#if defined(FASTLED_SUPPORT)
#if defined(ARDUINO)
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#else
#include <string.h>
#include <stdio.h>
#endif
#include <stdlib.h>
#else
// FASTLED not defined: compile as empty stub to avoid linker errors
#endif

#if defined(FASTLED_SUPPORT)
// FastLED support implementation with APA102 (bit-banged) and WS2812 (Adafruit_NeoPixel).
// Supports multiple instances identified by a 16-bit identifier.

#define MAX_FASTLED_INSTANCES 4

struct fastled_instance_t {
    uint16_t id;
    uint16_t data_pin;
    uint16_t clock_pin; // only for APA102
    uint8_t  type; // FASTLED_TYPE_*
    uint16_t num_leds;
    uint8_t *buf; // RGB bytes (num_leds * 3)
    uint8_t brightness; // 0-255 brightness
    Adafruit_NeoPixel *neopixel; // for WS2812
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
            g_instances[i].neopixel = NULL;
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
    if (inst->neopixel) {
        delete inst->neopixel;
        inst->neopixel = NULL;
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
    return "FASTLED_SUPPORT";
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

#if defined(ARDUINO)
// WS2812 send using Adafruit_NeoPixel library
static void ws2812_send(struct fastled_instance_t *inst) {
    if (!inst || !inst->neopixel || !inst->buf) return;
    
    // Apply brightness scaling and copy to NeoPixel buffer
    for (uint16_t i = 0; i < inst->num_leds; ++i) {
        uint8_t r = (uint8_t)((uint16_t)inst->buf[i*3 + 0] * inst->brightness / 255);
        uint8_t g = (uint8_t)((uint16_t)inst->buf[i*3 + 1] * inst->brightness / 255);
        uint8_t b = (uint8_t)((uint16_t)inst->buf[i*3 + 2] * inst->brightness / 255);
        inst->neopixel->setPixelColor(i, inst->neopixel->Color(r, g, b));
    }
    inst->neopixel->show();
}
#endif

bool fastled_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        // APA102 commands (0x011X)
        case 0x0110: // CMD_APA102_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_instance(id)) { cmd_send_ok(); return true; }
                struct fastled_instance_t *inst = alloc_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->type = FASTLED_TYPE_APA102;
                cmd_send_ok();
            }
            return true;
        case 0x0111: // CMD_APA102_SETUP
            // payload: id(2) + data_pin + clock_pin + num_leds(2)
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t data_pin = (uint16_t)payload[2];
                uint16_t clock_pin = (uint16_t)payload[3];
                uint16_t num_leds = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                
                inst->data_pin = data_pin;
                inst->clock_pin = clock_pin;
                inst->num_leds = num_leds;
                
                // Allocate buffer
                if (inst->buf) { free(inst->buf); inst->buf = NULL; }
                if (num_leds > 0) {
                    inst->buf = (uint8_t*)malloc((size_t)num_leds * 3);
                    if (!inst->buf) { inst->num_leds = 0; cmd_send_error(); return true; }
                    memset(inst->buf, 0, (size_t)num_leds * 3);
                }
                
                cmd_send_ok();
            }
            return true;
        case 0x0115: // CMD_APA102_SHOW
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_APA102) { cmd_send_error(); return true; }
                const uint8_t *data = &payload[2];
                uint16_t data_len = (uint16_t)(len - 2);
                uint16_t expected = (uint16_t)(inst->num_leds * 3);
                if (data_len < expected) {
                    uint16_t to_copy = data_len < expected ? data_len : expected;
                    if (inst->buf && to_copy) memcpy(inst->buf, data, to_copy);
                } else {
                    if (inst->buf && expected) memcpy(inst->buf, data, expected);
                }

                // Send OK BEFORE apa102_send() for consistency with WS2812
                cmd_send_ok();
#if defined(ARDUINO)
                apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
#endif
            }
            return true;
        case 0x0116: // CMD_APA102_SET_BRIGHTNESS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t brightness = payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_APA102) { cmd_send_error(); return true; }
                inst->brightness = brightness;
                // Send OK BEFORE apa102_send() for consistency with WS2812
                cmd_send_ok();
#if defined(ARDUINO)
                if (inst->buf && inst->num_leds > 0) {
                    apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
                }
#endif
            }
            return true;
        
        // WS2812 commands (0x012X)
        case 0x0120: // CMD_WS2812_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_instance(id)) { cmd_send_ok(); return true; }
                struct fastled_instance_t *inst = alloc_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->type = FASTLED_TYPE_WS2812;
                cmd_send_ok();
            }
            return true;
        case 0x0121: // CMD_WS2812_SETUP
            // payload: id(2) + data_pin + num_leds(2)
            if (len < 5) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t data_pin = (uint16_t)payload[2];
                uint16_t num_leds = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                
                inst->data_pin = data_pin;
                inst->num_leds = num_leds;
                
                // Allocate buffer
                if (inst->buf) { free(inst->buf); inst->buf = NULL; }
                if (num_leds > 0) {
                    inst->buf = (uint8_t*)malloc((size_t)num_leds * 3);
                    if (!inst->buf) { inst->num_leds = 0; cmd_send_error(); return true; }
                    memset(inst->buf, 0, (size_t)num_leds * 3);
                }
                
#if defined(ARDUINO)
                // Initialize NeoPixel
                if (inst->neopixel) {
                    delete inst->neopixel;
                }
                inst->neopixel = new Adafruit_NeoPixel(num_leds, data_pin, NEO_GRB + NEO_KHZ800);
                if (inst->neopixel) {
                    inst->neopixel->begin();
                    inst->neopixel->clear();
                    inst->neopixel->show();
                }
#endif
                
                cmd_send_ok();
            }
            return true;
        case 0x0125: // CMD_WS2812_SHOW
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_WS2812) { cmd_send_error(); return true; }
                const uint8_t *data = &payload[2];
                uint16_t data_len = (uint16_t)(len - 2);
                uint16_t expected = (uint16_t)(inst->num_leds * 3);
                if (data_len < expected) {
                    uint16_t to_copy = data_len < expected ? data_len : expected;
                    if (inst->buf && to_copy) memcpy(inst->buf, data, to_copy);
                } else {
                    if (inst->buf && expected) memcpy(inst->buf, data, expected);
                }

                // Send OK BEFORE ws2812_send() to avoid serial timing issues
                // neopixel->show() disables interrupts, preventing serial transmission
                cmd_send_ok();
#if defined(ARDUINO)
                ws2812_send(inst);
#endif
            }
            return true;
        case 0x0126: // CMD_WS2812_SET_BRIGHTNESS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t brightness = payload[2];
                struct fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_WS2812) { cmd_send_error(); return true; }
                inst->brightness = brightness;
                // Send OK BEFORE ws2812_send() to avoid serial timing issues
                cmd_send_ok();
#if defined(ARDUINO)
                if (inst->buf && inst->num_leds > 0) {
                    ws2812_send(inst);
                }
#endif
            }
            return true;
        default:
            return false;
    }
}

// Helper functions for debug module
bool fastled_create_debug_instance(uint16_t instance_id, uint16_t data_pin, uint16_t clock_pin, uint8_t led_type) {
    // Check if instance already exists
    if (find_instance(instance_id)) {
        return true; // already exists
    }
    
    // Allocate new instance
    struct fastled_instance_t *inst = alloc_instance(instance_id);
    if (!inst) {
        return false; // no space
    }
    
    // Configure for single LED
    inst->data_pin = data_pin;
    inst->clock_pin = clock_pin;
    inst->type = led_type;
    inst->num_leds = 1;
    inst->brightness = 255; // full brightness
    
    // Allocate buffer for 1 LED (3 bytes RGB)
    inst->buf = (uint8_t*)malloc(3);
    if (!inst->buf) {
        free_instance(inst);
        return false;
    }
    memset(inst->buf, 0, 3); // start with LED off
    
    // Validate config for APA102
    if (inst->type == FASTLED_TYPE_APA102 && inst->clock_pin == 0xFFFF) {
        free_instance(inst);
        return false;
    }

    return true;
}

bool fastled_set_single_led(uint16_t instance_id, uint8_t r, uint8_t g, uint8_t b) {
    struct fastled_instance_t *inst = find_instance(instance_id);
    if (!inst || !inst->buf || inst->num_leds != 1) {
        return false; // instance not found or not configured for single LED
    }
    
    // Set RGB values in buffer
    inst->buf[0] = r;
    inst->buf[1] = g;
    inst->buf[2] = b;
    
#if defined(ARDUINO)
    // Send to LED based on type
    if (inst->type == FASTLED_TYPE_APA102) {
        apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
    } else if (inst->type == FASTLED_TYPE_WS2812) {
        // For now, WS2812 is not implemented in bit-banging
        // This would require precise timing which is challenging without a library
        // TODO: Add WS2812 bit-banging implementation or use Adafruit_NeoPixel library
        // For debugging purposes, you might want to add Adafruit NeoPixel library to platformio.ini:
        // lib_deps = adafruit/Adafruit NeoPixel@^1.10.0
        return false; // not yet supported
    }
#endif
    
    return true;
}

#else // !FASTLED_SUPPORT

// Stub implementations when FASTLED_SUPPORT is not defined
bool fastled_create_debug_instance(uint16_t instance_id, uint16_t data_pin, uint16_t clock_pin, uint8_t led_type) {
    (void)instance_id; (void)data_pin; (void)clock_pin; (void)led_type;
    return false;
}

bool fastled_set_single_led(uint16_t instance_id, uint8_t r, uint8_t g, uint8_t b) {
    (void)instance_id; (void)r; (void)g; (void)b;
    return false;
}

#endif // FASTLED_SUPPORT
