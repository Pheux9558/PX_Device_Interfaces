// Command parsing + lightweight dispatcher
#include "cmd.h"
#include "cmd_auto.h"
#include "dispatch.h"
#include "serial.h"
#include "../../serial_rtos/src/serial_rtos.h"
#include <string.h>

// Legacy range-based handler table (kept for API compatibility)
#define CMD_MAX_HANDLERS 12
struct handler_entry { uint16_t start; uint16_t end; cmd_handler_t h; };
static struct handler_entry g_handlers[CMD_MAX_HANDLERS];
static int g_handler_count = 0;

// simple circular buffer for incoming bytes
// Larger buffer is required for LCD bitmap packets.
#define CMD_BUFSZ 2048
static uint8_t g_buf[CMD_BUFSZ];
static size_t g_buf_len = 0;

void cmd_init() {
    g_handler_count = 0;
    g_buf_len = 0;
    // Initialize hash-table dispatch
    cmd_dispatch_init();
    // Register all handlers declared with CMD_REGISTER() in service files
    cmd_auto_register_all();
}

bool cmd_register_handler(uint16_t start, uint16_t end, cmd_handler_t handler) {
    if (g_handler_count >= CMD_MAX_HANDLERS) return false;
    g_handlers[g_handler_count].start = start;
    g_handlers[g_handler_count].end = end;
    g_handlers[g_handler_count].h = handler;
    ++g_handler_count;
    
    // Populate hash-table dispatch (Phase 2.5)
    // Attempt to use O(1) hash dispatch first
    if (!cmd_dispatch_register(start, end, handler)) {
        // If registration fails (e.g., range spans multiple high-bytes),
        // fall back to legacy range-scan at dispatch time
        // (range-scan code still in place as fallback)
    }
    
    return true;
}

static uint8_t compute_checksum(uint16_t cmd, uint16_t len, const uint8_t *payload) {
    uint32_t sum = cmd + len;
    for (uint16_t i = 0; i < len; ++i) sum += payload[i];
    return (uint8_t)(sum & 0xFF);
}

void cmd_send_response(uint16_t rcmd, const uint8_t *payload, uint16_t rlen) {
    uint8_t frame[1 + 2 + 2 + CMD_BUFSZ + 1];
    if (rlen > CMD_BUFSZ) {
        rlen = CMD_BUFSZ;
    }

    uint8_t hdr[5];
    hdr[0] = 0xAA;
    hdr[1] = (uint8_t)(rcmd & 0xFF);
    hdr[2] = (uint8_t)((rcmd >> 8) & 0xFF);
    hdr[3] = (uint8_t)(rlen & 0xFF);
    hdr[4] = (uint8_t)((rlen >> 8) & 0xFF);
    memcpy(frame, hdr, sizeof(hdr));
    if (payload && rlen) {
        memcpy(&frame[5], payload, rlen);
    }
    uint8_t chk = compute_checksum(rcmd, rlen, payload ? payload : (const uint8_t*)"\0");
    frame[5 + rlen] = chk;

    // Use queued TX path when RTOS transport is active.
    if (g_response_queue != NULL) {
        if (serial_write_rtos(frame, (size_t)(6 + rlen)) > 0) {
            return;
        }
    }

    // Fallback for early boot/non-RTOS contexts.
    serial_write(frame, (size_t)(6 + rlen));
}

void cmd_send_ok() { uint16_t code = 0x1000; cmd_send_response(code, NULL, 0); }
void cmd_send_error() { uint16_t code = 0x1001; cmd_send_response(code, NULL, 0); }

bool cmd_verify_checksum(const uint8_t *buf, size_t len) {
    if (!buf || len < 6) return false;
    uint16_t payload_len = (uint16_t)buf[3] | ((uint16_t)buf[4] << 8);
    size_t expected = 1 + 2 + 2 + payload_len + 1;
    if (len < expected) return false;
    uint16_t cmd = (uint16_t)buf[1] | ((uint16_t)buf[2] << 8);
    uint8_t chk = buf[5 + payload_len];
    uint32_t sum = cmd + payload_len;
    for (size_t i = 0; i < payload_len; ++i) sum += buf[5 + i];
    return ((uint8_t)(sum & 0xFF)) == chk;
}

uint16_t cmd_extract_cmd(const uint8_t *buf) { return (uint16_t)buf[1] | ((uint16_t)buf[2] << 8); }
uint16_t cmd_extract_len(const uint8_t *buf) { return (uint16_t)buf[3] | ((uint16_t)buf[4] << 8); }

// process any complete packets present in internal buffer
static void _process_buffer() {
    size_t pos = 0;
    while (g_buf_len - pos >= 6) {
        if (g_buf[pos] != 0xAA) { pos++; continue; }
        if (pos + 5 >= g_buf_len) break;
        uint16_t cmd = cmd_extract_cmd(&g_buf[pos]);
        uint16_t payload_len = cmd_extract_len(&g_buf[pos]);
        size_t total_len = 1 + 2 + 2 + (size_t)payload_len + 1;
        if (pos + total_len > g_buf_len) break; // wait for full packet
        if (!cmd_verify_checksum(&g_buf[pos], total_len)) { pos++; continue; }
        const uint8_t *payload = &g_buf[pos + 5];
        bool handled = false;
        
        // Phase 2.5: Try O(1) hash-table dispatch first
        handled = cmd_dispatch_execute(cmd, payload, payload_len);
        
        // Fallback: Legacy range-scan if hash dispatch didn't handle it
        // (for ranges that span multiple high-bytes, which hash table doesn't support)
        if (!handled) {
            for (int i = 0; i < g_handler_count; ++i) {
                if (cmd >= g_handlers[i].start && cmd <= g_handlers[i].end) {
                    if (g_handlers[i].h) {
                        handled = g_handlers[i].h(cmd, payload, payload_len);
                    }
                    break;
                }
            }
        }
        
        if (!handled) {
            // unknown command -> send error
            cmd_send_error();
        }
        pos += total_len;
    }
    // compact buffer
    if (pos > 0) {
        if (pos < g_buf_len) memmove(g_buf, &g_buf[pos], g_buf_len - pos);
        g_buf_len -= pos;
    }
}

void cmd_process_bytes(const uint8_t *data, size_t len) {
    if (!data || len == 0) return;
    // append into ring-like buffer (simple)
    size_t to_copy = len;
    if (g_buf_len + to_copy > CMD_BUFSZ) {
        // drop oldest bytes to make room
        size_t drop = (g_buf_len + to_copy) - CMD_BUFSZ;
        if (drop >= g_buf_len) { g_buf_len = 0; }
        else { memmove(g_buf, &g_buf[drop], g_buf_len - drop); g_buf_len -= drop; }
    }
    memcpy(&g_buf[g_buf_len], data, to_copy);
    g_buf_len += to_copy;
    _process_buffer();
}
