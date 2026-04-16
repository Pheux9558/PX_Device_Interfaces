// FreeRTOS-based serial transport layer implementation
// Tasks: RxTask (reads from serial), TxTask (writes to serial)
#include "serial_rtos.h"
#include "../../serial/src/serial.h"
#include <string.h>
#include <Arduino.h>

// Packet framing constants (from px_device_interfaces/GPIO_Lib.py)
#define CMD_START_BYTE          0xAA
#define MIN_PACKET_SIZE         6   // start(1) + cmd(2) + len(2) + chk(1) = 6 minimum

// Packet item for queues: wraps variable-length data with size prefix
typedef struct {
    uint16_t size;                  // Actual size of data[0..size-1]
    uint8_t data[2048];             // Max packet size
} packet_item_t;

// Global queue handles accessible to other modules
rtosal_queue_t g_cmd_queue = NULL;
rtosal_queue_t g_response_queue = NULL;

// Task handles (for potential cleanup/deletion)
static rtosal_task_t g_rx_task = NULL;
static rtosal_task_t g_tx_task = NULL;

// RxTask scratch buffer for assembling packets
static uint8_t rx_buffer[2048];
static size_t rx_buffer_idx = 0;
static packet_item_t rx_pkt;
static packet_item_t tx_pkt;

// ===== Helper: Parse frame size from RxTask buffer
// Returns: full packet size (including START_BYTE) if valid frame exists at buf[0],
//          or 0 if incomplete/invalid
static size_t serial_rtos_find_frame_size(const uint8_t *buf, size_t buf_len) {
    if (buf_len < MIN_PACKET_SIZE || buf[0] != CMD_START_BYTE) {
        return 0;
    }
    
    if (buf_len < 5) {
        return 0;  // need at least start + cmd(2) + len(2) to read payload size
    }
    
    // Extract LEN from bytes 3-4 (little-endian)
    uint16_t cmd = (buf[2] << 8) | buf[1];
    uint16_t payload_len = (buf[4] << 8) | buf[3];
    
    // Total packet size: 1 + 2 + 2 + payload + 1
    size_t total_size = 1 + 2 + 2 + payload_len + 1;
    
    if (buf_len < total_size) {
        return 0;  // incomplete frame
    }
    
    // Check checksum: (cmd + len + sum(payload)) & 0xFF
    uint32_t sum = cmd + payload_len;
    for (uint16_t i = 0; i < payload_len; i++) {
        sum += buf[5 + i];
    }
    uint8_t computed_chk = (uint8_t)(sum & 0xFF);
    uint8_t packet_chk = buf[5 + payload_len];
    
    if (computed_chk != packet_chk) {
        return 0;  // checksum mismatch
    }
    
    return total_size;  // valid frame
}

// ===== RxTask: reads serial bytes and posts complete packets to cmd_queue
static void rx_task_fn(void *arg) {
    (void)arg;
    
    // RxTask runs indefinitely, reading from serial and buffering packets
    while (1) {
        // Read available bytes from serial one by one (non-blocking)
        while (serial_available() > 0 && rx_buffer_idx < sizeof(rx_buffer)) {
            int c = serial_read();
            if (c < 0) break;
            
            uint8_t byte = (uint8_t)c;
            
            rx_buffer[rx_buffer_idx++] = byte;
            
            // Check if we have a complete valid frame
            size_t frame_size = serial_rtos_find_frame_size(rx_buffer, rx_buffer_idx);
            if (frame_size > 0) {
                // Post the packet to cmd_queue
                rx_pkt.size = frame_size;
                memcpy(rx_pkt.data, rx_buffer, frame_size);
                rtosal_queue_send(g_cmd_queue, (const void *)&rx_pkt, 0);
                
                // Shift any remaining bytes after the frame
                if (rx_buffer_idx > frame_size) {
                    memmove(rx_buffer, rx_buffer + frame_size, rx_buffer_idx - frame_size);
                    rx_buffer_idx -= frame_size;
                } else {
                    rx_buffer_idx = 0;
                }
            }
        }
        
        // Block briefly to avoid spinning (let other tasks run)
        // In a real implementation, this would block on an ISR notification
        rtosal_delay_ms(1);
    }
}

// ===== TxTask: drains response_queue and writes to serial
static void tx_task_fn(void *arg) {
    (void)arg;
    
    while (1) {
        // Block waiting for a response packet
        rtosal_status_t status = rtosal_queue_receive(g_response_queue, (void *)&tx_pkt, 100);
        
        if (status == RTOSAL_OK && tx_pkt.size > 0) {
            // We have a packet; send it
            size_t written = serial_write(tx_pkt.data, tx_pkt.size);
            (void)written;  // Could track write errors here
        }
        // If timeout, just loop and try again
    }
}

// ===== Public API
void serial_rtos_begin(unsigned long baud) {
    // Initialize base serial layer
    serial_begin(baud);
    
    // Create queues
    // cmd_queue: carries serial packets (phase 1.1: fixed struct with size)
    rtosal_queue_config_t cmd_queue_cfg = {
        .depth = 8,
        .item_size = sizeof(packet_item_t)
    };
    rtosal_queue_create(&cmd_queue_cfg, &g_cmd_queue);
    
    // response_queue: carries response packets from dispatch
    rtosal_queue_config_t response_queue_cfg = {
        .depth = 32,
        .item_size = sizeof(packet_item_t)
    };
    rtosal_queue_create(&response_queue_cfg, &g_response_queue);
    
    if (g_cmd_queue == NULL || g_response_queue == NULL) {
        // Failed to create queues; in Phase 1.1 with stubs, this is expected
        // Phase 2+ when real RTOSAL is implemented, we'll have actual queues
        return;
    }
    
    // Create RxTask (HIGH priority - process serial input ASAP)
    rtosal_task_config_t rx_cfg = {
        .name = "RxTask",
        .fn = rx_task_fn,
        .arg = NULL,
        .stack_words = 8192,
        .priority = 3  // HIGH (assuming 0=LOW, 1=NORMAL, 2=HIGH, 3=CRITICAL)
    };
    rtosal_task_create(&rx_cfg, &g_rx_task);
    
    // Create TxTask (HIGH priority - drain response queue ASAP)
    rtosal_task_config_t tx_cfg = {
        .name = "TxTask",
        .fn = tx_task_fn,
        .arg = NULL,
        .stack_words = 4096,
        .priority = 3  // HIGH
    };
    rtosal_task_create(&tx_cfg, &g_tx_task);
}

void serial_rtos_end() {
    if (g_rx_task != NULL) {
        rtosal_task_delete(g_rx_task);
        g_rx_task = NULL;
    }
    if (g_tx_task != NULL) {
        rtosal_task_delete(g_tx_task);
        g_tx_task = NULL;
    }
    if (g_cmd_queue != NULL) {
        rtosal_queue_delete(g_cmd_queue);
        g_cmd_queue = NULL;
    }
    if (g_response_queue != NULL) {
        rtosal_queue_delete(g_response_queue);
        g_response_queue = NULL;
    }
}

rtosal_status_t serial_rtos_post_response(const uint8_t *buf, size_t len) {
    if (g_response_queue == NULL) {
        return RTOSAL_ERROR;
    }
    if (len > 2048) {
        return RTOSAL_ERROR;  // packet too large
    }
    
    packet_item_t pkt;
    pkt.size = len;
    memcpy(pkt.data, buf, len);
    
    return rtosal_queue_send(g_response_queue, (const void *)&pkt, 0);
}

size_t serial_write_rtos(const uint8_t *buf, size_t len) {
    if (serial_rtos_post_response(buf, len) == RTOSAL_OK) {
        return len;
    }
    return 0;
}

