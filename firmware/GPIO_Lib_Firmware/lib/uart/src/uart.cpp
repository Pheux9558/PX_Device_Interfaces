// UART RTOS Service - Phase 3 Task Implementation
// Queue-based per-instance UART management with RX buffering and serial I/O
#include "uart.h"
#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"
#include "../../rtosal/src/rtosal.h"
#include <string.h>

#if defined(ARDUINO)
/* HAL replaces direct HardwareSerial vendor calls.  ESP32 port: hal_port_esp32.cpp */
#include "../../hal/src/hal_uart.h"

// Self-register UART command handler (0x02xx range) with the dispatch system.
CMD_REGISTER(0x0200, 0x020F, uart_cmd_handler)

#define MAX_UART_INSTANCES 2
#define UART_RX_BUFFER_SIZE 256
#define UART_TASK_POLL_INTERVAL_MS 10

// Per-instance UART state
typedef struct {
    uint16_t id;
    int8_t tx_pin;
    int8_t rx_pin;
    uint32_t baudrate;
    uint8_t data_bits;
    uint8_t parity;
    uint8_t stop_bits;
    uint8_t flow_control;
    bool used;
    bool active;
    
    // RX ring buffer
    uint8_t rx_buffer[UART_RX_BUFFER_SIZE];
    uint16_t rx_head;
    uint16_t rx_tail;
} uart_instance_t;

// All UART service state bundled into one struct — owned by UartTask.
// The task is created with &g_uart_state as its arg so ownership is explicit.
// The mutex serialises competing accesses from DispatchTask (cmd handler) and UartTask (RX poll).
typedef struct {
    uart_instance_t instances[MAX_UART_INSTANCES];
} uart_state_t;

static uart_state_t   g_uart_state;
static rtosal_mutex_t g_uart_mutex = NULL;
static rtosal_task_t  g_uart_task  = NULL;

// Forward declarations
static void uart_task_fn(void *arg);

// Helper: Find instance by ID
static uart_instance_t *uart_find_instance(uart_state_t *s, uint16_t id) {
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        if (s->instances[i].used && s->instances[i].id == id) return &s->instances[i];
    }
    return NULL;
}

// Helper: Allocate new instance
static uart_instance_t *uart_alloc_instance(uart_state_t *s, uint16_t id) {
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        if (!s->instances[i].used) {
            memset(&s->instances[i], 0, sizeof(uart_instance_t));
            s->instances[i].used         = true;
            s->instances[i].id           = id;
            s->instances[i].tx_pin       = -1;
            s->instances[i].rx_pin       = -1;
            s->instances[i].baudrate     = 115200;
            s->instances[i].data_bits    = 8;
            s->instances[i].parity       = 0;
            s->instances[i].stop_bits    = 1;
            s->instances[i].flow_control = 0;
            s->instances[i].active       = false;
            s->instances[i].rx_head      = 0;
            s->instances[i].rx_tail      = 0;
            return &s->instances[i];
        }
    }
    return NULL;
}

// Helper: Configure and begin uart instance
static void uart_begin_if_ready(uart_instance_t *inst) {
    if (!inst || inst->active) return;
    if (inst->tx_pin < 0 || inst->rx_pin < 0) return;
    
    hal_uart_config_t cfg;
    cfg.baudrate     = inst->baudrate;
    cfg.data_bits    = inst->data_bits;
    cfg.parity       = inst->parity;
    cfg.stop_bits    = inst->stop_bits;
    cfg.flow_control = inst->flow_control;
    cfg.tx_pin       = inst->tx_pin;
    cfg.rx_pin       = inst->rx_pin;
    if (hal_uart_open((uint8_t)inst->id, &cfg) == HAL_STATUS_OK) {
        inst->active = true;
    }
}

// Helper: RX ring buffer operations
static void uart_rx_buffer_put(uart_instance_t *inst, uint8_t byte) {
    uint16_t next = (inst->rx_head + 1) % UART_RX_BUFFER_SIZE;
    if (next != inst->rx_tail) {
        inst->rx_buffer[inst->rx_head] = byte;
        inst->rx_head = next;
    }
}

static uint16_t uart_rx_buffer_get(uart_instance_t *inst, uint8_t *buf, uint16_t max_len) {
    uint16_t count = 0;
    while (count < max_len && inst->rx_tail != inst->rx_head) {
        buf[count++] = inst->rx_buffer[inst->rx_tail];
        inst->rx_tail = (inst->rx_tail + 1) % UART_RX_BUFFER_SIZE;
    }
    return count;
}

static uint16_t uart_rx_buffer_available(uart_instance_t *inst) {
    if (inst->rx_head >= inst->rx_tail) {
        return inst->rx_head - inst->rx_tail;
    } else {
        return UART_RX_BUFFER_SIZE - (inst->rx_tail - inst->rx_head);
    }
}

// UARTTask main loop: periodic RX buffering
// The task arg is a pointer to uart_state_t — the task is the sole owner of that state.
static void uart_task_fn(void *arg) {
    uart_state_t *s = (uart_state_t *)arg;

    modules_add_flag("UART");

    rtosal_tick_t wake_time = rtosal_now_ticks();

    while (1) {
        // Lock while draining HW FIFO into RX ring buffers
        rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
        for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
            uart_instance_t *inst = &s->instances[i];
            if (!inst->used || !inst->active) continue;

            uint8_t tmp[64];
            size_t n = 0;
            hal_uart_read((uint8_t)inst->id, tmp, sizeof(tmp), &n);
            for (size_t j = 0; j < n; j++) {
                uart_rx_buffer_put(inst, tmp[j]);
            }
        }
        rtosal_mutex_unlock(g_uart_mutex);

        rtosal_delay_until(&wake_time, UART_TASK_POLL_INTERVAL_MS);
    }
}

// Command handler: process UART commands (0x02xx range).
// Runs on DispatchTask — acquires g_uart_mutex before touching shared instance state.
bool uart_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    uart_state_t *s = &g_uart_state;
    switch (cmd) {
        case 0x0200: // CMD_UART_CREATE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                bool exists = (uart_find_instance(s, id) != NULL);
                if (!exists) exists = (uart_alloc_instance(s, id) != NULL);
                rtosal_mutex_unlock(g_uart_mutex);
                if (!exists) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0201: // CMD_UART_SET_PARITY
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t parity = payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->parity = parity; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0202: // CMD_UART_SET_STOPBITS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t stopbits = payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->stop_bits = stopbits; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0203: // CMD_UART_SET_DATA_BITS
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t databits = payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->data_bits = databits; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0204: // CMD_UART_SET_FLOWCONTROL
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint8_t flowcontrol = payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) inst->flow_control = flowcontrol;
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0205: // CMD_UART_SET_BAUDRATE
            if (len < 6) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint32_t baudrate = (uint32_t)payload[2] |
                                   ((uint32_t)payload[3] << 8) |
                                   ((uint32_t)payload[4] << 16) |
                                   ((uint32_t)payload[5] << 24);
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->baudrate = baudrate; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0206: // CMD_UART_SET_PIN_TX
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                int8_t tx_pin = (int8_t)payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->tx_pin = tx_pin; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0207: // CMD_UART_SET_PIN_RX
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                int8_t rx_pin = (int8_t)payload[2];
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) { inst->rx_pin = rx_pin; uart_begin_if_ready(inst); }
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                cmd_send_ok();
            }
            return true;

        case 0x0208: // CMD_UART_READ
            if (len < 4) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t read_len = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                uint8_t tmp[256];
                uint16_t actual = 0;
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                if (inst) actual = uart_rx_buffer_get(inst, tmp, (read_len > 256) ? 256 : read_len);
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                uint8_t resp[258];
                resp[0] = (uint8_t)(id & 0xFF);
                resp[1] = (uint8_t)((id >> 8) & 0xFF);
                memcpy(&resp[2], tmp, actual);
                cmd_send_response(0x0208, resp, 2 + actual);
            }
            return true;

        case 0x0209: // CMD_UART_WRITE
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                uint16_t write_len = len - 2;
                rtosal_mutex_lock(g_uart_mutex, RTOSAL_MAX_DELAY);
                uart_instance_t *inst = uart_find_instance(s, id);
                rtosal_mutex_unlock(g_uart_mutex);
                if (!inst) { cmd_send_error(); return true; }
                hal_uart_write((uint8_t)inst->id, &payload[2], write_len, NULL);
                cmd_send_ok();
            }
            return true;

        default:
            return false;
    }
}

// Module info string
const char *uart_module_flags(void) {
    return "UART";
}

// Initialize UART task
void gpio_uart_init(void) {
    // Initialise all instances to unused
    for (int i = 0; i < MAX_UART_INSTANCES; ++i) {
        g_uart_state.instances[i].used = false;
    }

    // Create mutex that serialises cmd-handler vs UartTask access to g_uart_state
    rtosal_mutex_create(&g_uart_mutex);

    // Create UARTTask; pass &g_uart_state so the task explicitly owns the state
    rtosal_task_config_t cfg = {
        .name        = "uart_task",
        .fn          = uart_task_fn,
        .arg         = &g_uart_state,
        .stack_words = 4096,
        .priority    = 1,
    };
    rtosal_task_create(&cfg, &g_uart_task);
}

#else // !defined(ARDUINO)

void gpio_uart_init(void) {
}

bool uart_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    (void)cmd;
    (void)payload;
    (void)len;
    return false;
}

const char *uart_module_flags(void) {
    return "UART_STUBBED";
}

#endif
