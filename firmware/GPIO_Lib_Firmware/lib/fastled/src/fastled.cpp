#include "fastled.h"
#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"

#if defined(FASTLED_SUPPORT)
#if defined(ARDUINO)
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#else
#include <stdio.h>
#include <string.h>
#endif
#include <stdlib.h>
#endif

#if defined(FASTLED_SUPPORT)
CMD_REGISTER(0x0110, 0x012F, fastled_cmd_handler)

#define MAX_FASTLED_INSTANCES 4

typedef struct {
    uint16_t id;
    uint16_t data_pin;
    uint16_t clock_pin;
    uint8_t type;
    uint16_t num_leds;
    uint8_t *buf;
    uint8_t brightness;
#if defined(ARDUINO)
    Adafruit_NeoPixel *neopixel;
#endif
    bool used;
} fastled_instance_t;

static fastled_instance_t g_instances[MAX_FASTLED_INSTANCES];

static fastled_instance_t *find_instance(uint16_t id) {
    for (int i = 0; i < MAX_FASTLED_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) {
            return &g_instances[i];
        }
    }
    return NULL;
}

static fastled_instance_t *alloc_instance(uint16_t id) {
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
#if defined(ARDUINO)
            g_instances[i].neopixel = NULL;
#endif
            return &g_instances[i];
        }
    }
    return NULL;
}

static void free_instance(fastled_instance_t *inst) {
    if (!inst) {
        return;
    }
    if (inst->buf) {
        free(inst->buf);
        inst->buf = NULL;
    }
#if defined(ARDUINO)
    if (inst->neopixel) {
        delete inst->neopixel;
        inst->neopixel = NULL;
    }
#endif
    inst->used = false;
}

static bool ensure_buffer(fastled_instance_t *inst, uint16_t num_leds) {
    size_t size = (size_t)num_leds * 3;

    if (!inst) {
        return false;
    }
    if (inst->buf) {
        free(inst->buf);
        inst->buf = NULL;
    }
    inst->num_leds = num_leds;
    if (size == 0) {
        return true;
    }

    inst->buf = (uint8_t *)malloc(size);
    if (!inst->buf) {
        inst->num_leds = 0;
        return false;
    }
    memset(inst->buf, 0, size);
    return true;
}

#if defined(ARDUINO)
static void apa102_send(uint16_t data_pin, uint16_t clock_pin, const uint8_t *buf, uint16_t num_leds, uint8_t brightness) {
    if (data_pin == 0xFFFF || clock_pin == 0xFFFF || !buf) {
        return;
    }

    pinMode((int)data_pin, OUTPUT);
    pinMode((int)clock_pin, OUTPUT);
    digitalWrite((int)clock_pin, LOW);

    for (int i = 0; i < 4; ++i) {
        for (int bit = 7; bit >= 0; --bit) {
            (void)bit;
            digitalWrite((int)data_pin, LOW);
            digitalWrite((int)clock_pin, HIGH);
            digitalWrite((int)clock_pin, LOW);
        }
    }

    for (uint16_t led = 0; led < num_leds; ++led) {
        uint8_t r = buf[led * 3 + 0];
        uint8_t g = buf[led * 3 + 1];
        uint8_t b = buf[led * 3 + 2];
        uint8_t global_brightness = (uint8_t)(0xE0 | ((brightness >> 3) & 0x1F));
        uint8_t frame[4] = {global_brightness, b, g, r};

        for (int j = 0; j < 4; ++j) {
            for (int bit = 7; bit >= 0; --bit) {
                digitalWrite((int)data_pin, (frame[j] >> bit) & 0x01);
                digitalWrite((int)clock_pin, HIGH);
                digitalWrite((int)clock_pin, LOW);
            }
        }
    }

    for (int i = 0; i < 4; ++i) {
        for (int bit = 7; bit >= 0; --bit) {
            (void)bit;
            digitalWrite((int)data_pin, HIGH);
            digitalWrite((int)clock_pin, HIGH);
            digitalWrite((int)clock_pin, LOW);
        }
    }
}

static void ws2812_send(fastled_instance_t *inst) {
    if (!inst || !inst->neopixel || !inst->buf) {
        return;
    }

    for (uint16_t i = 0; i < inst->num_leds; ++i) {
        uint8_t r = (uint8_t)((uint16_t)inst->buf[i * 3 + 0] * inst->brightness / 255);
        uint8_t g = (uint8_t)((uint16_t)inst->buf[i * 3 + 1] * inst->brightness / 255);
        uint8_t b = (uint8_t)((uint16_t)inst->buf[i * 3 + 2] * inst->brightness / 255);
        inst->neopixel->setPixelColor(i, inst->neopixel->Color(r, g, b));
    }
    inst->neopixel->show();
}
#endif
#endif

void fastled_init(void) {
#if defined(FASTLED_SUPPORT)
    for (int i = 0; i < MAX_FASTLED_INSTANCES; ++i) {
        g_instances[i].used = false;
        g_instances[i].buf = NULL;
#if defined(ARDUINO)
        g_instances[i].neopixel = NULL;
#endif
    }
    modules_add_flag(fastled_module_flags());
#endif
}

const char *fastled_module_flags(void) {
#if defined(FASTLED_SUPPORT)
    return "FASTLED_SUPPORT";
#else
    return "";
#endif
}

bool fastled_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
#if defined(FASTLED_SUPPORT)
    if (!payload && len) {
        cmd_send_error();
        return true;
    }

    switch (cmd) {
        case 0x0110:
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst) {
                    inst = alloc_instance(id);
                }
                if (!inst) {
                    cmd_send_error();
                    return true;
                }
                inst->type = FASTLED_TYPE_APA102;
                cmd_send_ok();
            }
            return true;

        case 0x0111:
            if (len < 6) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t data_pin = (uint16_t)payload[2];
                uint16_t clock_pin = (uint16_t)payload[3];
                uint16_t num_leds = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst) {
                    cmd_send_error();
                    return true;
                }
                inst->type = FASTLED_TYPE_APA102;
                inst->data_pin = data_pin;
                inst->clock_pin = clock_pin;
                if (!ensure_buffer(inst, num_leds)) {
                    cmd_send_error();
                    return true;
                }
                cmd_send_ok();
            }
            return true;

        case 0x0115:
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                uint16_t expected;
                const uint8_t *data;
                uint16_t data_len;
                if (!inst || inst->type != FASTLED_TYPE_APA102 || !inst->buf) {
                    cmd_send_error();
                    return true;
                }
                data = &payload[2];
                data_len = (uint16_t)(len - 2);
                expected = (uint16_t)(inst->num_leds * 3);
                if (data_len < expected) {
                    memcpy(inst->buf, data, data_len);
                } else if (expected > 0) {
                    memcpy(inst->buf, data, expected);
                }
                cmd_send_ok();
#if defined(ARDUINO)
                if (inst->num_leds > 0) {
                    apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
                }
#endif
            }
            return true;

        case 0x0116:
            if (len < 3) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_APA102) {
                    cmd_send_error();
                    return true;
                }
                inst->brightness = payload[2];
                cmd_send_ok();
#if defined(ARDUINO)
                if (inst->buf && inst->num_leds > 0) {
                    apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
                }
#endif
            }
            return true;

        case 0x0120:
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst) {
                    inst = alloc_instance(id);
                }
                if (!inst) {
                    cmd_send_error();
                    return true;
                }
                inst->type = FASTLED_TYPE_WS2812;
                cmd_send_ok();
            }
            return true;

        case 0x0121:
            if (len < 5) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t data_pin = (uint16_t)payload[2];
                uint16_t num_leds = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst) {
                    cmd_send_error();
                    return true;
                }
                inst->type = FASTLED_TYPE_WS2812;
                inst->data_pin = data_pin;
                inst->clock_pin = 0xFFFF;
                if (!ensure_buffer(inst, num_leds)) {
                    cmd_send_error();
                    return true;
                }
#if defined(ARDUINO)
                if (inst->neopixel) {
                    delete inst->neopixel;
                    inst->neopixel = NULL;
                }
                inst->neopixel = new Adafruit_NeoPixel(num_leds, data_pin, NEO_GRB + NEO_KHZ800);
                if (!inst->neopixel) {
                    cmd_send_error();
                    return true;
                }
                inst->neopixel->begin();
                inst->neopixel->clear();
                inst->neopixel->show();
#endif
                cmd_send_ok();
            }
            return true;

        case 0x0125:
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                uint16_t expected;
                const uint8_t *data;
                uint16_t data_len;
                if (!inst || inst->type != FASTLED_TYPE_WS2812 || !inst->buf) {
                    cmd_send_error();
                    return true;
                }
                data = &payload[2];
                data_len = (uint16_t)(len - 2);
                expected = (uint16_t)(inst->num_leds * 3);
                if (data_len < expected) {
                    memcpy(inst->buf, data, data_len);
                } else if (expected > 0) {
                    memcpy(inst->buf, data, expected);
                }
                cmd_send_ok();
#if defined(ARDUINO)
                if (inst->num_leds > 0) {
                    ws2812_send(inst);
                }
#endif
            }
            return true;

        case 0x0126:
            if (len < 3) {
                cmd_send_error();
                return true;
            }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                fastled_instance_t *inst = find_instance(id);
                if (!inst || inst->type != FASTLED_TYPE_WS2812) {
                    cmd_send_error();
                    return true;
                }
                inst->brightness = payload[2];
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
#else
    (void)cmd;
    (void)payload;
    (void)len;
    return false;
#endif
}

bool fastled_create_debug_instance(uint16_t instance_id, uint16_t data_pin, uint16_t clock_pin, uint8_t led_type) {
#if defined(FASTLED_SUPPORT)
    fastled_instance_t *inst = find_instance(instance_id);
    if (!inst) {
        inst = alloc_instance(instance_id);
    }
    if (!inst) {
        return false;
    }

    inst->data_pin = data_pin;
    inst->clock_pin = clock_pin;
    inst->type = led_type;
    inst->brightness = 0xFF;
    if (!ensure_buffer(inst, 1)) {
        free_instance(inst);
        return false;
    }

#if defined(ARDUINO)
    if (inst->type == FASTLED_TYPE_WS2812) {
        if (inst->neopixel) {
            delete inst->neopixel;
            inst->neopixel = NULL;
        }
        inst->neopixel = new Adafruit_NeoPixel(1, data_pin, NEO_GRB + NEO_KHZ800);
        if (!inst->neopixel) {
            free_instance(inst);
            return false;
        }
        inst->neopixel->begin();
        inst->neopixel->clear();
        inst->neopixel->show();
    }
#endif
    return true;
#else
    (void)instance_id;
    (void)data_pin;
    (void)clock_pin;
    (void)led_type;
    return false;
#endif
}

bool fastled_set_single_led(uint16_t instance_id, uint8_t r, uint8_t g, uint8_t b) {
#if defined(FASTLED_SUPPORT)
    fastled_instance_t *inst = find_instance(instance_id);
    if (!inst || !inst->buf || inst->num_leds != 1) {
        return false;
    }

    inst->buf[0] = r;
    inst->buf[1] = g;
    inst->buf[2] = b;

#if defined(ARDUINO)
    if (inst->type == FASTLED_TYPE_APA102) {
        apa102_send(inst->data_pin, inst->clock_pin, inst->buf, inst->num_leds, inst->brightness);
        return true;
    }
    if (inst->type == FASTLED_TYPE_WS2812) {
        ws2812_send(inst);
        return true;
    }
#endif
    return true;
#else
    (void)instance_id;
    (void)r;
    (void)g;
    (void)b;
    return false;
#endif
}
