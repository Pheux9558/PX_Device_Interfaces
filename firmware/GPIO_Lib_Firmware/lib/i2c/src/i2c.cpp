// I2C Service - Phase 4 bootstrap implementation
#include "i2c.h"
#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"

#if defined(I2C_SUPPORT)
CMD_REGISTER(0x0210, 0x021F, i2c_cmd_handler)
#endif

#if defined(ARDUINO) && defined(I2C_SUPPORT)

#include <Arduino.h>
#include <stdlib.h>

#define MAX_I2C_INSTANCES 2

static i2c_instance_t g_instances[MAX_I2C_INSTANCES];

#if defined(ESP32)
static TwoWire g_wire0(0);
static TwoWire g_wire1(1);
#endif

static TwoWire *wire_for_id(uint16_t id) {
#if defined(ESP32)
    if (id == 0) return &g_wire0;
    if (id == 1) return &g_wire1;
    return NULL;
#elif defined(ARDUINO_ARCH_RENESAS)
    if (id == 0) return &Wire;
    if (id == 1) {
        extern TwoWire Wire1;
        return &Wire1;
    }
    return NULL;
#else
    if (id == 0) return &Wire;
    return NULL;
#endif
}

i2c_instance_t *i2c_get_instance(uint16_t id) {
    for (int i = 0; i < MAX_I2C_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    }
    return NULL;
}

static i2c_instance_t *alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_I2C_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].wire_id = 0;
            g_instances[i].wire = wire_for_id(0);
            g_instances[i].scl = -1;
            g_instances[i].sda = -1;
            g_instances[i].freq = 100000;
            return &g_instances[i];
        }
    }
    return NULL;
}

static void i2c_begin_if_ready(i2c_instance_t *inst) {
    if (!inst || !inst->wire) return;
#if defined(ESP32)
    if (inst->scl < 0 || inst->sda < 0) return;
    inst->wire->begin(inst->sda, inst->scl, inst->freq);
#else
    inst->wire->begin();
#endif
}

void i2c_init(void) {
    for (int i = 0; i < MAX_I2C_INSTANCES; ++i) {
        g_instances[i].used = false;
    }
    modules_add_flag(i2c_module_flags());
}

const char *i2c_module_flags(void) {
    return "I2C_SUPPORT";
}

bool i2c_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0210: // CMD_I2C_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (i2c_get_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0211: // CMD_I2C_SET_FREQUENCY
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint32_t freq = (uint32_t)payload[2] | ((uint32_t)payload[3] << 8)
                              | ((uint32_t)payload[4] << 16) | ((uint32_t)payload[5] << 24);
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->freq = freq;
                i2c_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;

        case 0x0212: // CMD_I2C_SET_PIN_CLOCK
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? ((uint16_t)payload[2] | ((uint16_t)payload[3] << 8)) : payload[2];
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->scl = (int8_t)pin;
                i2c_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;

        case 0x0213: // CMD_I2C_SET_PIN_DATA
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? ((uint16_t)payload[2] | ((uint16_t)payload[3] << 8)) : payload[2];
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->sda = (int8_t)pin;
                i2c_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;

        case 0x021D: // CMD_I2C_SET_BUS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t bus_id = payload[2];
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                if (bus_id > 1) { cmd_send_error(); return true; }
                inst->wire_id = bus_id;
                inst->wire = wire_for_id(bus_id);
                if (!inst->wire) { cmd_send_error(); return true; }
                i2c_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;

        case 0x0214: // CMD_I2C_READ
            if (len < 5) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t addr = payload[2];
                uint16_t rlen = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst || !inst->wire) { cmd_send_error(); return true; }
                uint8_t *resp = (uint8_t *)malloc((size_t)rlen + 2);
                if (!resp) { cmd_send_error(); return true; }
                uint16_t got = 0;
                inst->wire->requestFrom((int)addr, (int)rlen);
                while (inst->wire->available() && got < rlen) {
                    resp[2 + got] = (uint8_t)inst->wire->read();
                    got++;
                }
                resp[0] = (uint8_t)(id & 0xFF);
                resp[1] = (uint8_t)((id >> 8) & 0xFF);
                cmd_send_response(0x0214, resp, (uint16_t)(got + 2));
                free(resp);
            }
            return true;

        case 0x0215: // CMD_I2C_WRITE
            if (len < 4) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t addr = payload[2];
                const uint8_t *data = &payload[3];
                uint16_t wlen = (uint16_t)(len - 3);
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst || !inst->wire) { cmd_send_error(); return true; }
                inst->wire->beginTransmission((int)addr);
                if (wlen > 0) inst->wire->write(data, (int)wlen);
                inst->wire->endTransmission();
                cmd_send_ok();
            }
            return true;

        case 0x0216: // CMD_I2C_WRITE_READ
            if (len < 7) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t addr = payload[2];
                uint16_t wlen = (uint16_t)payload[3] | ((uint16_t)payload[4] << 8);
                if (len < (uint16_t)(7 + wlen)) { cmd_send_error(); return true; }
                const uint8_t *wdata = &payload[5];
                uint16_t rlen = (uint16_t)payload[5 + wlen] | ((uint16_t)payload[6 + wlen] << 8);
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst || !inst->wire) { cmd_send_error(); return true; }
                inst->wire->beginTransmission((int)addr);
                if (wlen > 0) inst->wire->write(wdata, (int)wlen);
                inst->wire->endTransmission(false);
                uint8_t *resp = (uint8_t *)malloc((size_t)rlen + 2);
                if (!resp) { cmd_send_error(); return true; }
                uint16_t got = 0;
                inst->wire->requestFrom((int)addr, (int)rlen);
                while (inst->wire->available() && got < rlen) {
                    resp[2 + got] = (uint8_t)inst->wire->read();
                    got++;
                }
                resp[0] = (uint8_t)(id & 0xFF);
                resp[1] = (uint8_t)((id >> 8) & 0xFF);
                cmd_send_response(0x0216, resp, (uint16_t)(got + 2));
                free(resp);
            }
            return true;

        case 0x021E: // CMD_I2C_FULL_ADDRESS_SCAN
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                i2c_instance_t *inst = i2c_get_instance(id);
                if (!inst || !inst->wire) { cmd_send_error(); return true; }

                uint8_t resp[2 + 128];
                uint16_t count = 0;
                for (uint8_t addr = 0x03; addr <= 0x77; ++addr) {
                    inst->wire->beginTransmission((int)addr);
                    uint8_t err = inst->wire->endTransmission();
                    if (err == 0) {
                        if (count < 128) {
                            resp[2 + count] = addr;
                            count++;
                        }
                    }
                    delay(1);
                }

                resp[0] = (uint8_t)(id & 0xFF);
                resp[1] = (uint8_t)((id >> 8) & 0xFF);
                cmd_send_response(0x021E, resp, (uint16_t)(count + 2));
            }
            return true;

        default:
            return false;
    }
}

#else

void i2c_init(void) {}
const char *i2c_module_flags(void) { return "I2C_SUPPORT"; }
bool i2c_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    (void)cmd;
    (void)payload;
    (void)len;
    return false;
}

#endif
