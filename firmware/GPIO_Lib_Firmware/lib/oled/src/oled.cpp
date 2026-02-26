#include "oled.h"
#include "cmd.h"
#include "modules.h"
#include "spi.h"
#include "i2c.h"

#if defined(ARDUINO) && defined(OLED_SUPPORT)
#include <Arduino.h>
#include <stdlib.h>
#endif

#if defined(OLED_SUPPORT)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#endif

#if defined(OLED_SUPPORT)

#if !defined(I2C_SUPPORT)
inline i2c_instance_t *i2c_get_instance(uint16_t) { return NULL; }
#endif
#if !defined(SPI_SUPPORT)
inline gpio_lib_spi_instance_t *spi_get_instance(uint16_t) { return NULL; }
#endif

#define MAX_OLED_INSTANCES 2
// NOTE: Multiple display instances are not tested yet. Limit is 2 for now.

struct ssd1306_instance_t {
    uint16_t id;
    uint16_t width;
    uint16_t height;
    uint16_t i2c_id;
    uint16_t spi_id;
    uint8_t address;
    int8_t cs_pin;
    int8_t dc_pin;
    int8_t rst_pin;
    bool is_spi;
    bool stream_active;
    uint16_t stream_x;
    uint16_t stream_y;
    uint16_t stream_w;
    uint16_t stream_h;
    Adafruit_SSD1306 *display;
    bool used;
};

static ssd1306_instance_t g_instances[MAX_OLED_INSTANCES];

static ssd1306_instance_t *find_instance(uint16_t id) {
    for (int i = 0; i < MAX_OLED_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    }
    return NULL;
}

static ssd1306_instance_t *alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_OLED_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].width = 128;
            g_instances[i].height = 64;
            g_instances[i].i2c_id = 0;
            g_instances[i].spi_id = 0;
            g_instances[i].address = 0x3C;
            g_instances[i].cs_pin = -1;
            g_instances[i].dc_pin = -1;
            g_instances[i].rst_pin = -1;
            g_instances[i].is_spi = false;
            g_instances[i].stream_active = false;
            g_instances[i].stream_x = 0;
            g_instances[i].stream_y = 0;
            g_instances[i].stream_w = 0;
            g_instances[i].stream_h = 0;
            g_instances[i].display = NULL;
            return &g_instances[i];
        }
    }
    return NULL;
}

void oled_init() {
    for (int i = 0; i < MAX_OLED_INSTANCES; ++i) {
        g_instances[i].used = false;
        g_instances[i].display = NULL;
    }
    modules_add_flag(oled_module_flags());
}

const char *oled_module_flags() {
    return "OLED_SUPPORT";
}

static bool ssd1306_init_i2c(ssd1306_instance_t *inst) {
    if (!inst) return false;
    i2c_instance_t *i2c_inst = i2c_get_instance(inst->i2c_id);
    if (!i2c_inst || !i2c_inst->wire) return false;

    if (inst->display) { delete inst->display; inst->display = NULL; }
    inst->display = new Adafruit_SSD1306(inst->width, inst->height, i2c_inst->wire, inst->rst_pin);
    if (!inst->display) return false;
    if (!inst->display->begin(SSD1306_SWITCHCAPVCC, inst->address)) return false;

    inst->display->clearDisplay();
    inst->display->setTextSize(1);
    inst->display->setTextColor(SSD1306_WHITE);
    inst->display->display();
    return true;
}

static bool ssd1306_init_spi(ssd1306_instance_t *inst) {
    if (!inst) return false;
    gpio_lib_spi_instance_t *spi_inst = spi_get_instance(inst->spi_id);
    if (!spi_inst || !spi_inst->spi) return false;

    if (inst->display) { delete inst->display; inst->display = NULL; }
    inst->display = new Adafruit_SSD1306(inst->width, inst->height, spi_inst->spi, inst->dc_pin, inst->rst_pin, inst->cs_pin);
    if (!inst->display) return false;
    if (!inst->display->begin(SSD1306_SWITCHCAPVCC)) return false;

    inst->display->clearDisplay();
    inst->display->setTextSize(1);
    inst->display->setTextColor(SSD1306_WHITE);
    inst->display->display();
    return true;
}

bool ssd1306_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0050: // CMD_SSD1306_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0051: // CMD_SSD1306_SETUP_I2C
            if (len < 9) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t width = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t height = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                uint16_t i2c_id = (uint16_t)payload[6] | ((uint16_t)payload[7] << 8);
                uint8_t address = payload[8];
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (!i2c_get_instance(i2c_id)) { cmd_send_error(); return true; }
                inst->width = width;
                inst->height = height;
                inst->i2c_id = i2c_id;
                inst->address = address;
                inst->is_spi = false;
                if (!ssd1306_init_i2c(inst)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0052: // CMD_SSD1306_SETUP_SPI
            if (len < 11) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t width = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t height = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                uint16_t spi_id = (uint16_t)payload[6] | ((uint16_t)payload[7] << 8);
                int8_t cs = (int8_t)payload[8];
                int8_t dc = (int8_t)payload[9];
                int8_t rst = (int8_t)payload[10];
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (!spi_get_instance(spi_id)) { cmd_send_error(); return true; }
                inst->width = width;
                inst->height = height;
                inst->spi_id = spi_id;
                inst->cs_pin = cs;
                inst->dc_pin = dc;
                inst->rst_pin = rst;
                inst->is_spi = true;
                if (!ssd1306_init_spi(inst)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0055: // CMD_SSD1306_CLEAR
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                inst->display->clearDisplay();
                inst->display->display();
                cmd_send_ok();
            }
            return true;
        case 0x0056: // CMD_SSD1306_SET_CURSOR
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t x = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t y = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                inst->display->setCursor(x, y);
                cmd_send_ok();
            }
            return true;
        case 0x0057: // CMD_SSD1306_WRITE_TEXT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                for (uint16_t i = 0; i < text_len; ++i) {
                    inst->display->write(text[i]);
                }
                inst->display->display();
                cmd_send_ok();
            }
            return true;
        case 0x0059: // CMD_SSD1306_WRITE_BITMAP
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                uint8_t func = payload[2];

                if (func == 1) { // BITMAP_BEGIN
                    if (len < 11) { cmd_send_error(); return true; }
                    uint16_t x = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                    uint16_t y = (uint16_t)payload[5] | ((uint16_t)payload[6] << 8);
                    uint16_t width = (uint16_t)payload[7] | ((uint16_t)payload[8] << 8);
                    uint16_t height = (uint16_t)payload[9] | ((uint16_t)payload[10] << 8);
                    inst->stream_active = true;
                    inst->stream_x = x;
                    inst->stream_y = y;
                    inst->stream_w = width;
                    inst->stream_h = height;
                    inst->display->clearDisplay();
                    cmd_send_ok();
                    return true;
                }

                if (func == 2) { // BITMAP_ROW
                    if (len < 5) { cmd_send_error(); return true; }
                    if (!inst->stream_active) { cmd_send_error(); return true; }
                    uint16_t row_idx = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                    if (row_idx >= inst->stream_h) { cmd_send_error(); return true; }
                    uint16_t row_bytes = (uint16_t)(len - 5);
                    uint16_t expected = (uint16_t)((inst->stream_w + 7u) / 8u);
                    if (row_bytes != expected) { cmd_send_error(); return true; }

                    const uint8_t *data = &payload[5];
                    inst->display->drawBitmap((int16_t)inst->stream_x, (int16_t)(inst->stream_y + row_idx), data, inst->stream_w, 1, SSD1306_WHITE);
                    cmd_send_ok();
                    return true;
                }

                if (func == 3) { // BITMAP_END
                    inst->stream_active = false;
                    inst->display->display();
                    cmd_send_ok();
                    return true;
                }

                cmd_send_error();
            }
            return true;
        case 0x005A: // CMD_SSD1306_SET_BRIGHTNESS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t level = payload[2];
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                inst->display->ssd1306_command(SSD1306_SETCONTRAST);
                inst->display->ssd1306_command(level);
                cmd_send_ok();
            }
            return true;
        case 0x005B: // CMD_SSD1306_SET_ROTATION
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t rotation = payload[2];
                if (rotation > 3) { cmd_send_error(); return true; }
                ssd1306_instance_t *inst = find_instance(id);
                if (!inst || !inst->display) { cmd_send_error(); return true; }
                inst->display->setRotation(rotation);
                cmd_send_ok();
            }
            return true;
    }
    return false;
}
#else
void oled_init() {}
const char *oled_module_flags() { return ""; }
bool ssd1306_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif
