#include "uart.h"
#include "cmd.h"
#include "modules.h"

#if defined(ARDUINO) && defined(UART_SUPPORT)
#include <stdlib.h>

#if defined(ESP32)
#include <HardwareSerial.h>
#endif

#define MAX_UART_INSTANCES 2

struct uart_instance_t {
    uint16_t id;
#if defined(ESP32)
    HardwareSerial *serial;
#else
    Stream *serial;
#endif
    int8_t tx_pin;
    int8_t rx_pin;
    uint32_t baud;
    uint8_t data_bits;
    uint8_t parity;
    uint8_t stop_bits;
    uint8_t flow;
    bool used;
};

static uart_instance_t g_instances[MAX_UART_INSTANCES];

#if defined(ESP32)
static HardwareSerial *serial_for_id(uint16_t id) {
    if (id == 0) return &Serial1;
    if (id == 1) return &Serial2;
    return NULL;
}
#else
static Stream *serial_for_id(uint16_t id) {
    if (id == 0) return &Serial;
    return NULL;
}
#endif

static uart_instance_t *uart_get_instance(uint16_t id) {
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        if (g_instances[i].used && g_instances[i].id == id) return &g_instances[i];
    }
    return NULL;
}

static uart_instance_t *uart_alloc_instance(uint16_t id) {
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        if (!g_instances[i].used) {
            g_instances[i].used = true;
            g_instances[i].id = id;
            g_instances[i].tx_pin = -1;
            g_instances[i].rx_pin = -1;
            g_instances[i].baud = 115200;
            g_instances[i].data_bits = 8;
            g_instances[i].parity = 0;
            g_instances[i].stop_bits = 1;
            g_instances[i].flow = 0;
#if defined(ESP32)
            g_instances[i].serial = serial_for_id(id);
#else
            g_instances[i].serial = serial_for_id(id);
#endif
            return &g_instances[i];
        }
    }
    return NULL;
}

#if defined(ESP32)
static uint32_t uart_config_from_params(uint8_t data_bits, uint8_t parity, uint8_t stop_bits) {
    if (data_bits == 7) {
        if (parity == 1 && stop_bits == 2) return SERIAL_7E2;
        if (parity == 1) return SERIAL_7E1;
        if (parity == 2) return SERIAL_7O1;
        return SERIAL_7N1;
    }
    // default 8-bit
    if (parity == 1 && stop_bits == 2) return SERIAL_8E2;
    if (parity == 1) return SERIAL_8E1;
    if (parity == 2 && stop_bits == 2) return SERIAL_8O2;
    if (parity == 2) return SERIAL_8O1;
    if (stop_bits == 2) return SERIAL_8N2;
    return SERIAL_8N1;
}
#endif

static void uart_begin_if_ready(uart_instance_t *inst) {
    if (!inst) return;
#if defined(ESP32)
    if (!inst->serial) return;
    if (inst->tx_pin < 0 || inst->rx_pin < 0) return;
    uint32_t config = uart_config_from_params(inst->data_bits, inst->parity, inst->stop_bits);
    inst->serial->begin(inst->baud, config, inst->rx_pin, inst->tx_pin);
#else
    (void)inst;
#endif
}

void uart_init() {
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        g_instances[i].used = false;
    }
    modules_add_flag(uart_module_flags());
}

const char *uart_module_flags() {
    return "UART_SUPPORT";
}

bool uart_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    if (!payload && len) { cmd_send_error(); return true; }
    switch (cmd) {
        case 0x0200: // CMD_UART_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                if (uart_get_instance(id)) { cmd_send_ok(); return true; }
                if (!uart_alloc_instance(id)) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;
        case 0x0201: // CMD_UART_SET_PARITY
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t parity = payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->parity = parity;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0202: // CMD_UART_SET_STOPBITS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t stopbits = payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->stop_bits = stopbits;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0203: // CMD_UART_SET_DATA_BITS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t databits = payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->data_bits = databits;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0204: // CMD_UART_SET_FLOWCONTROL
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t flow = payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->flow = flow;
                cmd_send_ok();
            }
            return true;
        case 0x0205: // CMD_UART_SET_BAUDRATE
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint32_t baud = (uint32_t)payload[2] | ((uint32_t)payload[3] << 8) | ((uint32_t)payload[4] << 16) | ((uint32_t)payload[5] << 24);
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->baud = baud;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0206: // CMD_UART_SET_PIN_TX
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? (uint16_t)payload[2] | ((uint16_t)payload[3] << 8) : payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->tx_pin = (int8_t)pin;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0207: // CMD_UART_SET_PIN_RX
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t pin = (len >= 4) ? (uint16_t)payload[2] | ((uint16_t)payload[3] << 8) : payload[2];
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst) { cmd_send_error(); return true; }
                inst->rx_pin = (int8_t)pin;
                uart_begin_if_ready(inst);
                cmd_send_ok();
            }
            return true;
        case 0x0208: // CMD_UART_READ
            if (len < 4) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t rlen = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst || !inst->serial) { cmd_send_error(); return true; }
                uint8_t *resp = (uint8_t *)malloc((size_t)rlen + 2);
                if (!resp) { cmd_send_error(); return true; }
                uint16_t got = 0;
#if defined(ESP32)
                while (inst->serial->available() && got < rlen) {
                    int c = inst->serial->read();
                    if (c < 0) break;
                    resp[2 + got] = (uint8_t)c;
                    got++;
                }
#else
                while (inst->serial->available() && got < rlen) {
                    int c = inst->serial->read();
                    if (c < 0) break;
                    resp[2 + got] = (uint8_t)c;
                    got++;
                }
#endif
                resp[0] = (uint8_t)(id & 0xFF);
                resp[1] = (uint8_t)((id >> 8) & 0xFF);
                cmd_send_response(0x0208, resp, (uint16_t)(got + 2));
                free(resp);
            }
            return true;
        case 0x0209: // CMD_UART_WRITE
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uart_instance_t *inst = uart_get_instance(id);
                if (!inst || !inst->serial) { cmd_send_error(); return true; }
                const uint8_t *data = &payload[2];
                uint16_t wlen = (uint16_t)(len - 2);
                if (wlen > 0) inst->serial->write(data, wlen);
                cmd_send_ok();
            }
            return true;
        default:
            return false;
    }
}
#else
void uart_init() {}
const char *uart_module_flags() { return "UART_SUPPORT"; }
bool uart_cmd_handler(uint16_t, const uint8_t *, uint16_t) { return false; }
#endif
