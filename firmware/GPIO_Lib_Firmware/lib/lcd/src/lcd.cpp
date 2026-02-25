#include "lcd.h"
#include "cmd.h"
#include "modules.h"
#include "spi.h"
#include "i2c.h"

#if defined(ARDUINO) && (defined(LCD_SUPPORT) || defined(HD44780_SUPPORT) || defined(AIP31068L_SUPPORT))
#include <Arduino.h>
#include <stdlib.h>
#endif

#if defined(LCD_SUPPORT)
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#endif

#if defined(HD44780_SUPPORT) || defined(AIP31068L_SUPPORT)
#include <LiquidCrystal_I2C.h>
#endif

#define MAX_LCD_INSTANCES 2
// NOTE: Multiple display instances are not tested yet. Limit is 2 for now.

#if defined(LCD_SUPPORT)
struct st7735_instance_t {
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

static st7735_instance_t g_st7735_instances[MAX_LCD_INSTANCES];

static st7735_instance_t *find_st7735_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (g_st7735_instances[i].used && g_st7735_instances[i].id == id) return &g_st7735_instances[i];
    }
    return NULL;
}

static st7735_instance_t *alloc_st7735_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (!g_st7735_instances[i].used) {
            g_st7735_instances[i].used = true;
            g_st7735_instances[i].id = id;
            g_st7735_instances[i].spi_id = 0;
            g_st7735_instances[i].width = 0;
            g_st7735_instances[i].height = 0;
            g_st7735_instances[i].cs_pin = -1;
            g_st7735_instances[i].dc_pin = -1;
            g_st7735_instances[i].rst_pin = -1;
            g_st7735_instances[i].backlight_pin = -1;
            g_st7735_instances[i].backlight_inverted = false;
            g_st7735_instances[i].cursor_x = 0;
            g_st7735_instances[i].cursor_y = 0;
            g_st7735_instances[i].stream_active = false;
            g_st7735_instances[i].stream_x = 0;
            g_st7735_instances[i].stream_y = 0;
            g_st7735_instances[i].stream_w = 0;
            g_st7735_instances[i].stream_h = 0;
            g_st7735_instances[i].tft = NULL;
            return &g_st7735_instances[i];
        }
    }
    return NULL;
}

static void st7735_apply_backlight(st7735_instance_t *inst, uint8_t level) {
    if (!inst || inst->backlight_pin < 0) return;
    uint8_t val = inst->backlight_inverted ? (uint8_t)(255 - level) : level;
    if (val == 0 || val == 255) {
        digitalWrite(inst->backlight_pin, val ? HIGH : LOW);
    } else {
        analogWrite(inst->backlight_pin, val);
    }
}

static void st7735_init_display(st7735_instance_t *inst, gpio_lib_spi_instance_t *spi_inst) {
    if (!inst || !spi_inst) return;
    if (inst->tft) return;
    if (!spi_inst->spi) return;

    inst->tft = new Adafruit_ST7735(spi_inst->spi, inst->cs_pin, inst->dc_pin, inst->rst_pin);
    inst->tft->initR(INITR_MINI160x80);
    inst->tft->setRotation(0);
    inst->tft->fillScreen(ST77XX_BLACK);
}
#endif

#if defined(HD44780_SUPPORT) && defined(I2C_SUPPORT)
struct hd44780_instance_t {
    uint16_t id;
    uint16_t i2c_id;
    uint16_t cols;
    uint16_t rows;
    uint8_t address;
    LiquidCrystal_I2C *lcd;
    bool used;
};

static hd44780_instance_t g_hd44780_instances[MAX_LCD_INSTANCES];

static hd44780_instance_t *find_hd44780_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (g_hd44780_instances[i].used && g_hd44780_instances[i].id == id) return &g_hd44780_instances[i];
    }
    return NULL;
}

static hd44780_instance_t *alloc_hd44780_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (!g_hd44780_instances[i].used) {
            g_hd44780_instances[i].used = true;
            g_hd44780_instances[i].id = id;
            g_hd44780_instances[i].i2c_id = 0;
            g_hd44780_instances[i].cols = 16;
            g_hd44780_instances[i].rows = 2;
            g_hd44780_instances[i].address = 0x27;
            g_hd44780_instances[i].lcd = NULL;
            return &g_hd44780_instances[i];
        }
    }
    return NULL;
}
#endif

#if defined(AIP31068L_SUPPORT) && defined(I2C_SUPPORT)
struct aip31068l_instance_t {
    uint16_t id;
    uint16_t i2c_id;
    uint16_t cols;
    uint16_t rows;
    uint8_t address;
    LiquidCrystal_I2C *lcd;
    bool used;
};

static aip31068l_instance_t g_aip31068l_instances[MAX_LCD_INSTANCES];

static aip31068l_instance_t *find_aip31068l_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (g_aip31068l_instances[i].used && g_aip31068l_instances[i].id == id) return &g_aip31068l_instances[i];
    }
    return NULL;
}

static aip31068l_instance_t *alloc_aip31068l_instance(uint16_t id) {
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        if (!g_aip31068l_instances[i].used) {
            g_aip31068l_instances[i].used = true;
            g_aip31068l_instances[i].id = id;
            g_aip31068l_instances[i].i2c_id = 0;
            g_aip31068l_instances[i].cols = 16;
            g_aip31068l_instances[i].rows = 2;
            g_aip31068l_instances[i].address = 0x3E;
            g_aip31068l_instances[i].lcd = NULL;
            return &g_aip31068l_instances[i];
        }
    }
    return NULL;
}
#endif

void lcd_init() {
#if defined(LCD_SUPPORT)
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        g_st7735_instances[i].used = false;
        g_st7735_instances[i].tft = NULL;
    }
    modules_add_flag(lcd_module_flags());
#if defined(IPS_SUPPORT)
    modules_add_flag("IPS_SUPPORT");
#endif
#endif

#if defined(HD44780_SUPPORT) && defined(I2C_SUPPORT)
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        g_hd44780_instances[i].used = false;
        g_hd44780_instances[i].lcd = NULL;
    }
    modules_add_flag("HD44780_SUPPORT");
#endif

#if defined(AIP31068L_SUPPORT) && defined(I2C_SUPPORT)
    for (int i = 0; i < MAX_LCD_INSTANCES; ++i) {
        g_aip31068l_instances[i].used = false;
        g_aip31068l_instances[i].lcd = NULL;
    }
    modules_add_flag("AIP31068L_SUPPORT");
#endif
}

const char *lcd_module_flags() {
    return "LCD_SUPPORT";
}

#if defined(LCD_SUPPORT)
bool st7735_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0020: // CMD_ST7735_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_st7735_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_st7735_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0022: // CMD_ST7735_SETUP_SPI
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
                st7735_instance_t *inst = find_st7735_instance(id);
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

                gpio_lib_spi_instance_t *spi_inst = spi_get_instance(spi_id);
                if (!spi_inst) { cmd_send_error(); return true; }
                st7735_init_display(inst, spi_inst);
                cmd_send_ok();
            }
            return true;
        case 0x0025: // CMD_ST7735_CLEAR
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                st7735_instance_t *inst = find_st7735_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->tft->fillScreen(ST77XX_BLACK);
                inst->cursor_x = 0;
                inst->cursor_y = 0;
                cmd_send_ok();
            }
            return true;
        case 0x0026: // CMD_ST7735_SET_CURSOR
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t x = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t y = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                st7735_instance_t *inst = find_st7735_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->cursor_x = x;
                inst->cursor_y = y;
                cmd_send_ok();
            }
            return true;
        case 0x0027: // CMD_ST7735_WRITE_TEXT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                st7735_instance_t *inst = find_st7735_instance(id);
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
        case 0x0028: // CMD_ST7735_WRITE_TEXT_CENTER
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                st7735_instance_t *inst = find_st7735_instance(id);
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
        case 0x0029: // CMD_ST7735_WRITE_BITMAP
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t func = payload[2];
                st7735_instance_t *inst = find_st7735_instance(id);
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
                    for (uint16_t i = 0; i < inst->stream_w; ++i) {
                        uint16_t lo = data[i * 2];
                        uint16_t hi = data[i * 2 + 1];
                        pix[i] = (uint16_t)(lo | (hi << 8));
                    }
                    inst->tft->drawRGBBitmap(inst->stream_x, (int16_t)(inst->stream_y + row_idx), pix, inst->stream_w, 1);
                    free(pix);
                    cmd_send_ok();
                    return true;
                }

                if (func == 3) { // BITMAP_END
                    inst->stream_active = false;
                    cmd_send_ok();
                    return true;
                }

                cmd_send_error();
            }
            return true;
        case 0x002A: // CMD_ST7735_SET_BACKLIGHT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t level = payload[2];
                st7735_instance_t *inst = find_st7735_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                st7735_apply_backlight(inst, level);
                cmd_send_ok();
            }
            return true;
        case 0x002C: // CMD_ST7735_SET_ROTATION
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t rot = payload[2] & 0x03;
                st7735_instance_t *inst = find_st7735_instance(id);
                if (!inst || !inst->tft) { cmd_send_error(); return true; }
                inst->tft->setRotation(rot);
                cmd_send_ok();
            }
            return true;
    }
    return false;
}
#else
bool st7735_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif

#if defined(HD44780_SUPPORT)
bool hd44780_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0030: // CMD_HD44780_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_hd44780_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_hd44780_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0031: // CMD_HD44780_SETUP_I2C
            if (len < 9) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t cols = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t rows = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                uint16_t i2c_id = (uint16_t)payload[6] | ((uint16_t)payload[7] << 8);
                uint8_t address = payload[8];
                hd44780_instance_t *inst = find_hd44780_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (!i2c_get_instance(i2c_id)) { cmd_send_error(); return true; }
                inst->cols = cols;
                inst->rows = rows;
                inst->i2c_id = i2c_id;
                inst->address = address;
                if (inst->lcd) { delete inst->lcd; inst->lcd = NULL; }
                inst->lcd = new LiquidCrystal_I2C(address, cols, rows);
                inst->lcd->init();
                inst->lcd->backlight();
                cmd_send_ok();
            }
            return true;
        case 0x0035: // CMD_HD44780_CLEAR
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                hd44780_instance_t *inst = find_hd44780_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                inst->lcd->clear();
                cmd_send_ok();
            }
            return true;
        case 0x0036: // CMD_HD44780_SET_CURSOR
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t col = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t row = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                hd44780_instance_t *inst = find_hd44780_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                inst->lcd->setCursor(col, row);
                cmd_send_ok();
            }
            return true;
        case 0x0037: // CMD_HD44780_WRITE_TEXT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                hd44780_instance_t *inst = find_hd44780_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                for (uint16_t i = 0; i < text_len; ++i) {
                    inst->lcd->write(text[i]);
                }
                cmd_send_ok();
            }
            return true;
        case 0x003A: // CMD_HD44780_SET_BACKLIGHT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t level = payload[2];
                hd44780_instance_t *inst = find_hd44780_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                if (level) inst->lcd->backlight(); else inst->lcd->noBacklight();
                cmd_send_ok();
            }
            return true;
    }
    return false;
}
#else
bool hd44780_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif

#if defined(AIP31068L_SUPPORT)
bool aip31068l_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0040: // CMD_AIP31068L_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (find_aip31068l_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_aip31068l_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0041: // CMD_AIP31068L_SETUP_I2C
            if (len < 9) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t cols = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t rows = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                uint16_t i2c_id = (uint16_t)payload[6] | ((uint16_t)payload[7] << 8);
                uint8_t address = payload[8];
                aip31068l_instance_t *inst = find_aip31068l_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (!i2c_get_instance(i2c_id)) { cmd_send_error(); return true; }
                inst->cols = cols;
                inst->rows = rows;
                inst->i2c_id = i2c_id;
                inst->address = address;
                if (inst->lcd) { delete inst->lcd; inst->lcd = NULL; }
                inst->lcd = new LiquidCrystal_I2C(address, cols, rows);
                inst->lcd->init();
                inst->lcd->backlight();
                cmd_send_ok();
            }
            return true;
        case 0x0045: // CMD_AIP31068L_CLEAR
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                aip31068l_instance_t *inst = find_aip31068l_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                inst->lcd->clear();
                cmd_send_ok();
            }
            return true;
        case 0x0046: // CMD_AIP31068L_SET_CURSOR
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t col = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint16_t row = (uint16_t)payload[4] | ((uint16_t)payload[5] << 8);
                aip31068l_instance_t *inst = find_aip31068l_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                inst->lcd->setCursor(col, row);
                cmd_send_ok();
            }
            return true;
        case 0x0047: // CMD_AIP31068L_WRITE_TEXT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                const char *text = (const char *)&payload[2];
                uint16_t text_len = (uint16_t)(len - 2);
                aip31068l_instance_t *inst = find_aip31068l_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                for (uint16_t i = 0; i < text_len; ++i) {
                    inst->lcd->write(text[i]);
                }
                cmd_send_ok();
            }
            return true;
        case 0x004A: // CMD_AIP31068L_SET_BACKLIGHT
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t level = payload[2];
                aip31068l_instance_t *inst = find_aip31068l_instance(id);
                if (!inst || !inst->lcd) { cmd_send_error(); return true; }
                if (level) inst->lcd->backlight(); else inst->lcd->noBacklight();
                cmd_send_ok();
            }
            return true;
    }
    return false;
}
#else
bool aip31068l_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif
