// Command Dispatch Task - Phase 1.1 Implementation
// Reads packets from g_cmd_queue and dispatches to service handlers
#include "dispatch.h"
#include "cmd.h"
#include "../../serial_rtos/src/serial_rtos.h"
#include "../../serial/src/serial.h"
#include <string.h>

// Packet item struct (matches serial_rtos queue item)
typedef struct {
    uint16_t size;
    uint8_t data[2048];
} packet_item_t;

void dispatch_init(void) {
    // Phase 2.5: Initialize hash-table dispatch for O(1) command lookup
    cmd_dispatch_init();
    // cmd_register_handler() calls populate the hash table as handlers are registered
}

void dispatch_packet(void) {
    // Read one packet from g_cmd_queue (if available - non-blocking)
    if (g_cmd_queue == NULL) {
        // Compatibility fallback for non-RTOS targets: read directly from serial
        // and feed bytes into the command parser.
        uint8_t inbuf[256];
        size_t idx = 0;
        while (serial_available() > 0 && idx < sizeof(inbuf)) {
            int c = serial_read();
            if (c < 0) {
                break;
            }
            inbuf[idx++] = (uint8_t)c;
        }
        if (idx > 0) {
            cmd_process_bytes(inbuf, idx);
        }
        return;
    }
    
    packet_item_t pkt = {0};
    
    // Try to receive one packet (non-blocking, 0ms timeout)
    rtosal_status_t status = rtosal_queue_receive(g_cmd_queue, (void *)&pkt, 0);
    
    if (status != RTOSAL_OK) {
        return;  // No packet available, nothing to do
    }
    
    if (pkt.size < 6) {
        return;  // Packet too small to be valid
    }
    
    // Pass the full framed packet to parser/dispatcher.
    // cmd_process_bytes() handles buffer accumulation and hash-table dispatch.
    cmd_process_bytes(pkt.data, pkt.size);
}
