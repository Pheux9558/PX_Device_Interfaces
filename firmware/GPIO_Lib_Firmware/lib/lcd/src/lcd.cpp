#include "lcd.h"
#include "cmd.h"
#include "modules.h"
#include "spi.h"

#if defined(ARDUINO) && defined(LCD_SUPPORT)
#include <Arduino.h>
#include <stdlib.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>

#define MAX_LCD_INSTANCES 2

struct lcd_instance_t {
    uint16_t id;
    uint16_t spi_id;
    uint16_t width;
    uint16_t height;
    int8_t cs_pin;
    int8_t dc_pin;
    int8_t rst_pin;
    int8_t backlight_pin;
    bool backlight_inverted;
    uint16_t cursor_x;
    uint16_t cursor_y;
    bool stream_active;
    uint16_t stream_x;
    uint16_t stream_y;
    uint16_t stream_w;
    uint16_t stream_h;
    Adafruit_ST7735 *tft;
    bool used;
};

static lcd_instance_t g_instances[MAX_LCD_INSTANCES];

static lcd_instance_t *find_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    }
    return NULL;
}

static lcd_instance_t *alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].spi_id = 0;
            g_instances[i].width = 0;
            g_instances[i].height = 0;
            g_instances[i].cs_pin = -1;
            g_instances[i].dc_pin = -1;
            g_instances[i].rst_pin = -1;
            g_instances[i].backlight_pin = -1;
            g_instances[i].backlight_inverted = false;
            g_instances[i].cursor_x = 0;
            g_instances[i].cursor_y = 0;
            g_instances[i].stream_active = false;
            g_instances[i].stream_x = 0;
            g_instances[i].stream_y = 0;
            g_instances[i].stream_w = 0;
            g_instances[i].stream_h = 0;
            g_instances[i].tft = NULL;
            return &g_instances[i];
        }
    }
    return NULL;
}

void lcd_init() {
    // Turn Off LCD Backlight
    pinMode(38, OUTPUT);
    digitalWrite(38, HIGH);

    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        g_instances[i].used = false;
        g_instances[i].tft = NULL;
    }
    modules_add_flag(lcd_module_flags());
#if defined(IPS_SUPPORT)
    modules_add_flag("IPS_SUPPORT");
#endif
}

const char *lcd_module_flags() {
    return "LCD_SUPPORT";
}

static void lcd_apply_backlight(lcd_instance_t *inst, uint8_t level) {
    if (!inst || inst->backlight_pin < 0) return;
    uint8_t val = inst->backlight_inverted ? (uint8_t)(255 - level) : level;
    if (val == 0 || val == 255) {
        digitalWrite(inst->backlight_pin, val ? HIGH : LOW);
    } else {
        analogWrite(inst->backlight_pin, val);
    }
}

static void lcd_init_st7735(lcd_instance_t *inst, spi_instance_t *spi_inst) {
    if (!inst || !spi_inst) return;
    if (inst->tft) return;
    if (!spi_inst->spi) return;

    inst->tft = new Adafruit_ST7735(spi_inst->spi, inst->cs_pin, inst->dc_pin, inst->rst_pin);
    inst->tft->initR(INITR_MINI160x80);
    inst->tft->setRotation(0);
    inst->tft->fillScreen(ST77XX_BLACK);
}

bool lcd_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0020: // CMD_LCD_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0022: // CMD_LCD_SETUP_SPI
            if (len < 11) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t width = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t height = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                uint16_t spi_id = (uint16_t)payload[6] | ((uint16_t)payload[7] << 8);
                int8_t cs = (int8_t)payload[8];
                int8_t dc = (int8_t)payload[9];
                int8_t rst = (int8_t)payload[10];
                int8_t backlight = -1;
                bool inverted = false;
                if (len >= 13) {
                    backlight = (int8_t)payload[11];
                    inverted = payload[12] ? true : false;
                }
                lcd_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->width = width;
                inst->height = height;
                inst->spi_id = spi_id;
                inst->cs_pin = cs;
                inst->dc_pin = dc;
                inst->rst_pin = rst;
                inst->backlight_pin = backlight;
                inst->backlight_inverted = inverted;

                pinMode(inst->cs_pin, OUTPUT);
                pinMode(inst->dc_pin, OUTPUT);
                if (inst->rst_pin >= 0) pinMode(inst->rst_pin, OUTPUT);
                if (inst->backlight_pin >= 0) pinMode(inst->backlight_pin, OUTPUT);

                spi_instance_t *spi_inst = spi_get_instance(spi_id);
                if (!spi_inst) { cmd_send_error(); return true; }
                lcd_init_st7735(inst, spi_inst);
                cmd_send_ok();
            }
            return true;
        case 0x0025: // CMD_LCD_CLEAR
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->tft->fillScreen(ST77XX_BLACK);
                inst->cursor_x = 0;
                inst->cursor_y = 0;
                cmd_send_ok();
            }
            return true;
        case 0x0026: // CMD_LCD_SET_CURSOR
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t x = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t y = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->cursor_x = x;
                inst->cursor_y = y;
                cmd_send_ok();
            }
            return true;
        case 0x0027: // CMD_LCD_WRITE_TEXT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->tft->setCursor(inst->cursor_x, inst->cursor_y);
                inst->tft->setTextColor(ST77XX_WHITE, ST77XX_BLACK);
                inst->tft->setTextSize(1);
                for (uint16_t i = 0; i < text_len; ++i) {
                    inst->tft->write(text[i]);
                }
                cmd_send_ok();
            }
            return true;
        case 0x0028: // CMD_LCD_WRITE_TEXT_CENTER
        // [ ] TODO REWORK because broken
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                int16_t x1 = 0, y1 = 0;
                uint16_t w = 0, h = 0;
                inst->tft->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
                uint16_t x = (inst->width > w) ? (uint16_t)((inst->width - w) / 2) : 0;
                uint16_t y = inst->cursor_y;
                inst->tft->setCursor(x, y);
                inst->tft->setTextColor(ST77XX_WHITE, ST77XX_BLACK);
                inst->tft->setTextSize(1);
                for (uint16_t i = 0; i < text_len; ++i) {
                    inst->tft->write(text[i]);
                }
                cmd_send_ok();
            }
            return true;
        case 0x0029: // CMD_LCD_WRITE_BITMAP
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t func = payload[2];
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }

                if (func == 1) { // BITMAP_BEGIN
                    if (len < 11) { cmd_send_error(); return true; }
                    uint16_t x = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                    uint16_t y = (uint16_t)payload[5] | ((uint16_t)payload[6] << 8);
                    uint16_t w = (uint16_t)payload[7] | ((uint16_t)payload[8] << 8);
                    uint16_t h = (uint16_t)payload[9] | ((uint16_t)payload[10] << 8);
                    inst->stream_active = true;
                    inst->stream_x = x;
                    inst->stream_y = y;
                    inst->stream_w = w;
                    inst->stream_h = h;
                    cmd_send_ok();
                    return true;
                }

                if (func == 2) { // BITMAP_ROW
                    if (len < 5) { cmd_send_error(); return true; }
                    if (!inst->stream_active) { cmd_send_error(); return true; }
                    uint16_t row_idx = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                    if (row_idx >= inst->stream_h) { cmd_send_error(); return true; }
                    uint16_t row_bytes = (uint16_t)(len - 5);
                    uint16_t expected = (uint16_t)(inst->stream_w * 2u);
                    if (row_bytes != expected) { cmd_send_error(); return true; }

                    const uint8_t *data = &payload[5];
                    uint16_t *pix = (uint16_t *)malloc(expected);
                    if (!pix) { cmd_send_error(); return true; }
                    // Convert RGB565 to BGR565 and invert (transformation 5)
                    for (uint16_t i = 0; i < expected; i += 2) {
                        uint16_t rgb565 = (uint16_t)data[i] | ((uint16_t)data[i + 1] << 8);
                        uint16_t r = (rgb565 >> 11) & 0x1F;
                        uint16_t g = (rgb565 >> 5) & 0x3F;
                        uint16_t b = rgb565 & 0x1F;
                        uint16_t bgr565 = (b << 11) | (g << 5) | r;
                        pix[i / 2] = bgr565 ^ 0xFFFF;  // Invert bits
                    }
                    inst->tft->drawRGBBitmap(inst->stream_x, inst->stream_y + row_idx, pix, inst->stream_w, 1);
                    free(pix);
                    cmd_send_ok();
                    return true;
                }

                if (func == 3) { // BITMAP_END (also abort)
                    inst->stream_active = false;
                    inst->stream_w = 0;
                    inst->stream_h = 0;
                    cmd_send_ok();
                    return true;
                }

                cmd_send_error();
            }
            return true;
        case 0x002A: // CMD_LCD_SET_BRIHGHTNESS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t level = payload[2];
                lcd_instance_t *inst = find_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                lcd_apply_backlight(inst, level);
                cmd_send_ok();
            }
            return true;
        case 0x002C: // CMD_LCD_SET_ROTATION
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t rot = payload[2] & 0x03;
                lcd_instance_t *inst = find_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->tft->setRotation(rot);
                cmd_send_ok();
            }
            return true;
        default:
            return false;
    }
}
#else
void lcd_init() {}
const char *lcd_module_flags() { return "LCD_SUPPORT"; }
bool lcd_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif
