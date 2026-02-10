#include "spi.h"
#include "cmd.h"
#include "modules.h"

#if defined(ARDUINO) && defined(SPI_SUPPORT)
#include <Arduino.h>
#include <stdlib.h>

#define MAX_SPI_INSTANCES 2

static spi_instance_t g_instances[MAX_SPI_INSTANCES];

#if defined(ESP32)
#if defined(HSPI)
static SPIClass g_spi_hspi(HSPI);
#endif
#endif

static SPIClass *spi_for_id(uint16_t id) {
#if defined(ESP32)
    if (id == 0) return &SPI;
#if defined(HSPI)
    if (id == 1) return &g_spi_hspi;
#endif
    return NULL;
#else
    if (id == 0) return &SPI;
    return NULL;
#endif
}

spi_instance_t *spi_get_instance(uint16_t id) {
    for (int i = 0; i < MAX_SPI_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    }
    return NULL;
}

static spi_instance_t *alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_SPI_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].spi = spi_for_id(id);
            g_instances[i].sck = -1;
            g_instances[i].mosi = -1;
            g_instances[i].miso = -1;
            g_instances[i].freq = 1000000;
            g_instances[i].mode = 0;
            return &g_instances[i];
        }
    }
    return NULL;
}

static void spi_begin_if_ready(spi_instance_t *inst) {
    if (!inst || !inst->spi) return;
    if (inst->sck < 0 || inst->mosi < 0) return;
#if defined(ESP32)
    inst->spi->begin(inst->sck, inst->miso, inst->mosi, -1);
#else
    (void)inst;
    SPI.begin();
#endif
}

void spi_init() {
    for (int i = 0; i < MAX_SPI_INSTANCES; ++i) {
        g_instances[i].used = false;
    }
    modules_add_flag(spi_module_flags());
}

const char *spi_module_flags() {
    return "SPI_SUPPORT";
}

static void spi_transfer_bytes(spi_instance_t *inst, const uint8_t *tx, uint8_t *rx, uint16_t len) {
    if (!inst || !inst->spi) return;
    SPISettings settings(inst->freq, MSBFIRST, inst->mode & 0x03);
    inst->spi->beginTransaction(settings);
    for (uint16_t i = 0; i < len; ++i) {
        uint8_t v = inst->spi->transfer(tx ? tx[i] : 0x00);
        if (rx) rx[i] = v;
    }
    inst->spi->endTransaction();
}

bool spi_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0220: // CMD_SPI_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (spi_get_instance(id)) { cmd_send_ok(); return true; }
                if (!alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0221: // CMD_SPI_SET_FREQUENCY
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint32_t freq = (uint32_t)payload[2] | ((uint32_t)payload[3] << 8) | ((uint32_t)payload[4] << 16) | ((uint32_t)payload[5] << 24);
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->freq = freq;
                cmd_send_ok();
            }
            return true;
        case 0x0222: // CMD_SPI_SET_MODE
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t mode = payload[2];
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->mode = mode & 0x03;
                cmd_send_ok();
            }
            return true;
        case 0x0223: // CMD_SPI_SET_PIN_CLOCK
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? (uint16_t)payload[2] | ((uint16_t)payload[3] << 8) : payload[2];
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->sck = (int8_t)pin;
                spi_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0224: // CMD_SPI_SET_PIN_MOSI
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? (uint16_t)payload[2] | ((uint16_t)payload[3] << 8) : payload[2];
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->mosi = (int8_t)pin;
                spi_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0225: // CMD_SPI_SET_PIN_MISO
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? (uint16_t)payload[2] | ((uint16_t)payload[3] << 8) : payload[2];
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->miso = (int8_t)pin;
                spi_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0226: // CMD_SPI_READ (full-duplex transfer)
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                const uint8_t *tx = &payload[2];
                uint16_t tx_len = (uint16_t)(len - 2);
                if (tx_len == 0) { cmd_send_ok(); return true; }
                uint8_t *rx = (uint8_t *)malloc(tx_len + 2);
                if (!rx) { cmd_send_error(); return true; }
                spi_transfer_bytes(inst, tx, &rx[2], tx_len);
                rx[0] = (uint8_t)(id & 0xFF);
                rx[1] = (uint8_t)((id >> 8) & 0xFF);
                cmd_send_response(0x0226, rx, (uint16_t)(tx_len + 2));
                free(rx);
            }
            return true;
        case 0x0227: // CMD_SPI_WRITE
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                spi_instance_t *inst = spi_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                const uint8_t *tx = &payload[2];
                uint16_t tx_len = (uint16_t)(len - 2);
                if (tx_len > 0) {
                    spi_transfer_bytes(inst, tx, NULL, tx_len);
                }
                cmd_send_ok();
            }
            return true;
        default:
            return false;
    }
}
#else
void spi_init() {}
const char *spi_module_flags() { return "SPI_SUPPORT"; }
bool spi_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif
