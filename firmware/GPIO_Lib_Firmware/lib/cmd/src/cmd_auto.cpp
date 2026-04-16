// Self-registration linked list for command handlers.
// Service files use CMD_REGISTER() (from cmd_auto.h) to enqueue entries.
// cmd_init() calls cmd_auto_register_all() once to apply all registrations.
#include "cmd_auto.h"

static cmd_auto_node_t *g_head = NULL;

void cmd_auto_enqueue(cmd_auto_node_t *node) {
    if (!node) return;
    node->next = g_head;
    g_head = node;
}

void cmd_auto_register_all(void) {
    for (cmd_auto_node_t *n = g_head; n; n = n->next) {
        cmd_register_handler(n->start, n->end, n->handler);
    }
}
