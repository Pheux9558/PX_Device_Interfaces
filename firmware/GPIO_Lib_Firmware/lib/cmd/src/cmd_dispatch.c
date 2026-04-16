// O(1) Hash-Table Command Dispatch - Phase 2.5
// Replaces range-scan handler lookup with direct hash-table dispatch
// Hash function: index = (cmd >> 8) & 0xFF (command high-byte)
// No collisions: each high-byte value maps to exactly one entry
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "cmd.h"

// Hash table entry: indexed by command high-byte (0x00-0xFF)
typedef struct {
    uint16_t start;          // Start of command range (or 0xFFFF if unused)
    uint16_t end;            // End of command range
    cmd_handler_t handler;   // Handler function
    uint8_t is_registered;   // Whether this entry is in use
} cmd_dispatch_entry_t;

// Hash table: 256 entries, one per possible command high-byte value
static cmd_dispatch_entry_t g_dispatch_table[256];

// Initialize dispatch system (clear all entries)
void cmd_dispatch_init(void) {
    memset(g_dispatch_table, 0, sizeof(g_dispatch_table));
    for (int i = 0; i < 256; ++i) {
        g_dispatch_table[i].start = 0xFFFF;  // Mark as unregistered
        g_dispatch_table[i].is_registered = 0;
    }
}

// Register a handler for a command range [start..end]
// All commands in this range must share the same high-byte (start >> 8 == end >> 8)
// Returns true on success, false if range spans multiple high-bytes or table entry already used
bool cmd_dispatch_register(uint16_t start, uint16_t end, cmd_handler_t handler) {
    if (!handler) return false;
    
    // All commands in range must have same high-byte
    uint8_t start_high = (uint8_t)((start >> 8) & 0xFF);
    uint8_t end_high = (uint8_t)((end >> 8) & 0xFF);
    if (start_high != end_high) {
        // Range spans multiple high-bytes - not allowed in single entry
        // This would require multiple entries, which complicates the design
        // For Phase 2.5, require ranges to fit in one high-byte block
        return false;
    }
    
    // Get hash index from command high-byte
    uint8_t hash_index = start_high;
    
    // Check if entry already registered (would overwrite)
    if (g_dispatch_table[hash_index].is_registered) {
        // Could implement handler chaining here, but for now reject overwrite
        return false;
    }
    
    // Register entry
    g_dispatch_table[hash_index].start = start;
    g_dispatch_table[hash_index].end = end;
    g_dispatch_table[hash_index].handler = handler;
    g_dispatch_table[hash_index].is_registered = 1;
    
    return true;
}

// Look up handler for a command (O(1) hash lookup)
// Returns handler function pointer if found, NULL otherwise
cmd_handler_t cmd_dispatch_lookup(uint16_t cmd) {
    uint8_t hash_index = (uint8_t)((cmd >> 8) & 0xFF);
    cmd_dispatch_entry_t *entry = &g_dispatch_table[hash_index];
    
    // Check if entry is registered and command is in range
    if (entry->is_registered && cmd >= entry->start && cmd <= entry->end) {
        return entry->handler;
    }
    
    return NULL;  // Not found
}

// Execute handler for a command (returns true if handled)
bool cmd_dispatch_execute(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    cmd_handler_t handler = cmd_dispatch_lookup(cmd);
    if (handler) {
        return handler(cmd, payload, len);
    }
    return false;  // Unknown command
}
