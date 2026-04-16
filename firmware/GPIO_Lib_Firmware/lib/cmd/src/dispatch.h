// Command Dispatch Task - Phase 1.1 Implementation
// DispatchTask: reads packets from g_cmd_queue, routes to service handlers, queues responses
// This replaces the synchronous cmd_process_bytes() from the polling loop with async dispatch
// Phase 2.5: O(1) hash-table dispatch replaces range-scan lookup
#pragma once

#include <stdint.h>
#include <stdlib.h>
#include "cmd.h"

#ifdef __cplusplus
extern "C" {
#endif

// Initialize dispatch system (called from main before tasks run)
void dispatch_init(void);

// Main packet processing engine: reads from g_cmd_queue, calls handlers, queues responses
// Runs as a task and blocks until dispatched (will be replaced with true task in Phase 2)
void dispatch_packet(void);

// Phase 2.5: O(1) Hash-table dispatch functions
// Initialize hash table
void cmd_dispatch_init(void);

// Register a handler for a command range [start..end]
// All commands in range must share the same high-byte (start >> 8 == end >> 8)
bool cmd_dispatch_register(uint16_t start, uint16_t end, cmd_handler_t handler);

// Look up handler for a command (O(1) hash lookup via high-byte)
cmd_handler_t cmd_dispatch_lookup(uint16_t cmd);

// Execute handler for a command, returns true if handled
bool cmd_dispatch_execute(uint16_t cmd, const uint8_t *payload, uint16_t len);

#ifdef __cplusplus
}
#endif
