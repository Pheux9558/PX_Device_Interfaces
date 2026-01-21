// Command framing/dispatcher interface
#pragma once

#include <stdint.h>
#include <stddef.h>

// Packet framing: [0xAA][CMD(2)][LEN(2)][PAYLOAD...][CHK]

typedef bool (*cmd_handler_t)(uint16_t cmd, const uint8_t *payload, uint16_t len);

// initialize internal parser/dispatcher
void cmd_init();

// register a handler for a closed interval [start..end] (inclusive)
bool cmd_register_handler(uint16_t start, uint16_t end, cmd_handler_t handler);

// feed incoming bytes into the parser; this will parse complete packets
// and dispatch them to registered handlers. Safe to call from loop().
void cmd_process_bytes(const uint8_t *data, size_t len);

// helpers for building/sending responses (uses serial_write internally)
void cmd_send_response(uint16_t rcmd, const uint8_t *payload, uint16_t rlen);
void cmd_send_ok();
void cmd_send_error();

// low-level utilities (exposed for unit tests)
bool cmd_verify_checksum(const uint8_t *buf, size_t len);
uint16_t cmd_extract_cmd(const uint8_t *buf);
uint16_t cmd_extract_len(const uint8_t *buf);
