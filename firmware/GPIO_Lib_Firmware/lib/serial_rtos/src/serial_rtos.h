// FreeRTOS-based serial transport layer
// Separates RX (ISR → cmd_queue) from TX (response_queue → serial)
// Replaces blocking serial_write() calls with non-blocking queue posts
#pragma once

#include <stdint.h>
#include <stddef.h>
#include "../../rtosal/src/rtosal.h"

// Opaque queue handles used by dispatch and service tasks
extern rtosal_queue_t g_cmd_queue;          // RxTask → DispatchTask (serial packets)
extern rtosal_queue_t g_response_queue;     // Service → TxTask (response packets)

// Initialize the serial RTOS transport layer
// - Creates RxTask (HIGH priority) and TxTask (HIGH priority)
// - Initializes cmd_queue (depth 8) and response_queue (depth 32)
// - Attaches interrupt handlers for USB/UART serial input
// Call this during setup() instead of serial_begin()
void serial_rtos_begin(unsigned long baud);

// Shutdown serial RTOS transport layer
// - Deletes RxTask and TxTask
// - Destroys cmd_queue and response_queue
void serial_rtos_end();

// Post a response packet to the outgoing response queue (non-blocking)
// Used by dispatch or service tasks to send data back to host
// Returns: RTOSAL_OK if queued, RTOSAL_FULL if queue is full
rtosal_status_t serial_rtos_post_response(const uint8_t *buf, size_t len);

// Legacy backward compatibility: replace blocking serial_write() with queue post
// Returns: len if queued successfully, 0 if queue is full or not initialized
size_t serial_write_rtos(const uint8_t *buf, size_t len);
