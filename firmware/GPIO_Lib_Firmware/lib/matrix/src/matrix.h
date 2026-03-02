#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef ARDUINO_UNOR4_WIFI
  #include "Arduino_LED_Matrix.h"
  

  // Initialize the matrix module
  void matrix_init();
  
  // Update function for custom animations (call from main loop)
  bool matrix_update();

  // Main command handler dispatcher
  bool matrix_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);

  // Individual command handlers for Uno R4 Matrix
  bool matrix_create(const uint8_t *payload, uint16_t len);
  bool matrix_clear(const uint8_t *payload, uint16_t len);
  bool matrix_set_pixel(const uint8_t *payload, uint16_t len);
  bool matrix_write_text(const uint8_t *payload, uint16_t len);
  bool matrix_animation(const uint8_t *payload, uint16_t len);
  bool matrix_set_animation_frame(const uint8_t *payload, uint16_t len);
  
  // Custom frame/animation handlers (new commands)
  bool matrix_set_custom_frame(const uint8_t *payload, uint16_t len);
  bool matrix_show_custom_frame(const uint8_t *payload, uint16_t len);
  bool matrix_set_custom_animation(const uint8_t *payload, uint16_t len);
  bool matrix_show_custom_animation(const uint8_t *payload, uint16_t len);
  bool matrix_write_bitmap_direct(const uint8_t *payload, uint16_t len);

#endif // ARDUINO_UNOR4_WIFI
