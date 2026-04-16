// Self-registration macro for command handlers.
//
// Each service file places CMD_REGISTER(start, end, fn) at file scope.
// A GCC constructor (priority 101) enqueues the entry into a singly-linked list
// before setup()/main() runs.  cmd_init() calls cmd_auto_register_all() after
// cmd_dispatch_init() to process the list and register every declared handler.
//
// Usage (file scope, outside any function):
//   CMD_REGISTER(0x0200, 0x020F, uart_cmd_handler)
//
// Rules:
//   - Use each handler_fn token only once per translation unit.
//   - Wrap in the same #if guards used for the handler function itself.
#pragma once

#include <stdint.h>
#include "cmd.h"

#ifdef __cplusplus
extern "C" {
#endif

// Singly-linked list node for a pending handler registration.
typedef struct cmd_auto_node_s {
    uint16_t start;
    uint16_t end;
    cmd_handler_t handler;
    struct cmd_auto_node_s *next;   // zero-initialized by default for static variables
} cmd_auto_node_t;

// Append a node to the pending list.  Safe to call at any time before
// cmd_auto_register_all(), including from a GCC constructor.
void cmd_auto_enqueue(cmd_auto_node_t *node);

// Register all enqueued entries via cmd_register_handler().
// Called once by cmd_init() after the dispatch table has been initialized.
void cmd_auto_register_all(void);

#ifdef __cplusplus
}
#endif

// CMD_REGISTER(start_cmd, end_cmd, handler_fn)
//
// Creates a static node and a constructor that enqueues it before setup().
// Some toolchains/language servers reject constructor priority arguments,
// so we conditionally use the plain form there.
#define CMD_AUTO_CONSTRUCTOR __attribute__((constructor))

#define CMD_REGISTER(start_cmd, end_cmd, handler_fn)                        \
    static cmd_auto_node_t _cmd_node_##handler_fn = {                      \
        (start_cmd), (end_cmd), (handler_fn), (cmd_auto_node_t *)0         \
    };                                                                      \
    CMD_AUTO_CONSTRUCTOR                                                    \
    static void _cmd_auto_reg_##handler_fn(void) {                         \
        cmd_auto_enqueue(&_cmd_node_##handler_fn);                         \
    }
