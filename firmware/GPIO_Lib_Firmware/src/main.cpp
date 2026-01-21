#include <Arduino.h>
#include "serial.h"
#include "cmd.h"
#include "gpio.h"
#include "firmware.h"
#include "modules.h"
#include "board.h"
#include <string.h>
#include <stdio.h>


// Simple main that initializes subsystems and echoes valid packets

#if defined(DEBUG)
// forward GPIO debug callbacks to serial for visibility
static void debug_to_serial(const char *msg) {
  if (!msg) return;
  serial_write((const uint8_t *)msg, strlen(msg));
  const uint8_t nl[2] = {'\r', '\n'};
  serial_write(nl, 2);
}
#endif

void setup() {
  serial_begin(115200);
  // initialize modules registry first so module init() calls can register flags
  modules_init();

  // initialize board module so it can register board-specific flags
  board_init();

  gpio_init();

  // Initialize command dispatcher and register module handlers
  cmd_init();
  cmd_register_handler(0x0000, 0x00FF, gpio_cmd_handler); // gpio setup & similar
  cmd_register_handler(0xFFFD, 0xFFFF, firmware_cmd_handler);

  // register firmware's own flag
  modules_add_flag(firmware_module_flags());

#if defined(DEBUG)
  // set callback
  gpio_set_debug_cb(debug_to_serial);
#endif
  // send a ready banner so host can handshake and avoid race with bootloader
  const char *ready = "GPIO_READY\r\n";
  serial_write((const uint8_t *)ready, (size_t)strlen(ready));
}


static uint8_t checksum_for(uint16_t cmd, uint16_t len, const uint8_t *payload) {
  uint32_t sum = cmd + len;
  for (uint16_t i = 0; i < len; ++i) sum += payload[i];
  return (uint8_t)(sum & 0xFF);
}

void loop() {
  // read bytes from serial and pass them to the command dispatcher
  if (serial_available() > 0) {
    uint8_t inbuf[256];
    size_t idx = 0;
    while (serial_available() > 0 && idx < sizeof(inbuf)) {
      int c = serial_read();
      if (c < 0) break;
      inbuf[idx++] = (uint8_t)c;
    }
    if (idx) {
      cmd_process_bytes(inbuf, idx);
    }
  }


  delay(10);

  // Simple blink helper (paste into loop) - only enabled in DEBUG builds
#if defined(DEBUG)
  #if defined(ARDUINO_UNO)
    // on Arduino Uno, use pin 13
    static uint16_t blink_pin = 13;
  #elif defined(ESP32_PICO_D4)
    // on ESP32 Dev, use pin 10
    static uint16_t blink_pin = 10;
  #else
    // default blink pin
    static uint16_t blink_pin = 13;
  #endif
  static uint32_t blink_interval_ms = 5; // blink period in ms
  static uint32_t blink_last_ms = 0;
  static uint8_t  blink_state = 0;
  static bool     blink_inited = false;

  if (!blink_inited) {
    // ensure pin set as digital output once
    gpio_set_mode(blink_pin, 1);
    gpio_digital_write(blink_pin, 0);
    blink_inited = true;
    blink_last_ms = millis();
  }

  uint32_t now = millis();
  if ((uint32_t)(now - blink_last_ms) >= blink_interval_ms) {
    blink_state = (blink_state ? 0 : 1);
    gpio_digital_write(blink_pin, blink_state);
    blink_last_ms = now;
  }
#endif
}
