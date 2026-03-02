#include "matrix.h"
#include "cmd.h"
#include <string.h>

#ifdef ARDUINO_UNOR4_WIFI
  #ifdef MATRIX_WITH_ARDUINOGRAPHICS
    #include "ArduinoGraphics.h"
  #endif
#endif

#ifdef ARDUINO_UNOR4_WIFI
  static ArduinoLEDMatrix* g_matrix = nullptr;
  static uint8_t g_animation_frames[256][12];  // frame_number -> 12 bytes packed bitmap
  static bool g_animation_frame_valid[256];
  static uint8_t g_pixel_buffer[96];           // y*12 + x (0/1 per pixel)

  // Custom frame/animation storage (new) - reduced limits for memory constraints
  #define MAX_CUSTOM_FRAMES 16           // reduced from 64
  #define MAX_CUSTOM_ANIMATIONS 4
  #define MAX_FRAMES_PER_ANIMATION 8     // reduced from 16
  
  static uint8_t g_custom_frames[MAX_CUSTOM_FRAMES][12];      // custom frame 0-15 -> 12 bytes packed bitmap
  static bool g_custom_frame_valid[MAX_CUSTOM_FRAMES];
  
  // Custom animations (0-3), each can hold up to 8 frames
  struct CustomAnimation {
    uint8_t num_frames;
    bool loop;
    bool valid;
    uint8_t frames[MAX_FRAMES_PER_ANIMATION][12];  // up to 8 frames, 12 bytes each
  };
  static CustomAnimation g_custom_animations[MAX_CUSTOM_ANIMATIONS];
  
  // Animation state
  static uint8_t g_current_animation_id = 0xFF;  // 0xFF = no animation playing
  static uint8_t g_current_frame_idx = 0;
  static uint32_t g_last_frame_time = 0;
  static uint16_t g_frame_delay_ms = 100;  // default 100ms per frame (speed = 10 fps)

  static inline uint16_t pixel_index(uint8_t x, uint8_t y) {
    return (uint16_t)y * 12u + (uint16_t)x;
  }

  static void load_pixels_to_matrix() {
    if (g_matrix) {
      g_matrix->loadPixels(g_pixel_buffer, sizeof(g_pixel_buffer));
    }
  }

  static void packed12_to_pixels(const uint8_t packed[12], uint8_t out_pixels[96]) {
    memset(out_pixels, 0, 96);
    for (uint16_t bit_pos = 0; bit_pos < 96; ++bit_pos) {
      uint8_t byte_idx = bit_pos / 8;
      uint8_t bit_idx = bit_pos % 8;
      out_pixels[bit_pos] = (packed[byte_idx] >> bit_idx) & 0x01;
    }
  }

  static bool load_custom_frame_by_id(uint8_t frame_id) {
    if (!g_animation_frame_valid[frame_id]) {
      return false;
    }
    packed12_to_pixels(g_animation_frames[frame_id], g_pixel_buffer);
    load_pixels_to_matrix();
    return true;
  }

  static bool load_builtin_frame(uint8_t frame_id) {
    if (!g_matrix) {
      return false;
    }

    switch (frame_id) {
      case 0x00: g_matrix->loadFrame(LEDMATRIX_EMOJI_BASIC); return true;
      case 0x01: g_matrix->loadFrame(LEDMATRIX_EMOJI_HAPPY); return true;
      case 0x02: g_matrix->loadFrame(LEDMATRIX_EMOJI_SAD); return true;
      case 0x03: g_matrix->loadFrame(LEDMATRIX_HEART_BIG); return true;
      case 0x04: g_matrix->loadFrame(LEDMATRIX_HEART_SMALL); return true;
      case 0x05: g_matrix->loadFrame(LEDMATRIX_BOOTLOADER_ON); return true;
      case 0x06: g_matrix->loadFrame(LEDMATRIX_CLOUD_WIFI); return true;
      case 0x07: g_matrix->loadFrame(LEDMATRIX_BLUETOOTH); return true;
      case 0x08: g_matrix->loadFrame(LEDMATRIX_DANGER); return true;
      case 0x09: g_matrix->loadFrame(LEDMATRIX_CHIP); return true;
      case 0x0A: g_matrix->loadFrame(LEDMATRIX_LIKE); return true;
      case 0x0B: g_matrix->loadFrame(LEDMATRIX_MUSIC_NOTE); return true;
      case 0x0C: g_matrix->loadFrame(LEDMATRIX_RESISTOR); return true;
      case 0x0D: g_matrix->loadFrame(LEDMATRIX_UNO); return true;
      default: return false;
    }
  }

  static bool load_builtin_animation(uint8_t animation_id) {
    if (!g_matrix) {
      return false;
    }

    switch (animation_id) {
      case 0x00: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_STARTUP, sizeof(LEDMATRIX_ANIMATION_STARTUP)); return true;
      case 0x01: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_TETRIS_INTRO, sizeof(LEDMATRIX_ANIMATION_TETRIS_INTRO)); return true;
      case 0x02: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_ATMEGA, sizeof(LEDMATRIX_ANIMATION_ATMEGA)); return true;
      case 0x03: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_LED_BLINK_HORIZONTAL, sizeof(LEDMATRIX_ANIMATION_LED_BLINK_HORIZONTAL)); return true;
      case 0x04: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_LED_BLINK_VERTICAL, sizeof(LEDMATRIX_ANIMATION_LED_BLINK_VERTICAL)); return true;
      case 0x05: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_ARROWS_COMPASS, sizeof(LEDMATRIX_ANIMATION_ARROWS_COMPASS)); return true;
      case 0x06: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_AUDIO_WAVEFORM, sizeof(LEDMATRIX_ANIMATION_AUDIO_WAVEFORM)); return true;
      case 0x07: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_BATTERY, sizeof(LEDMATRIX_ANIMATION_BATTERY)); return true;
      case 0x08: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_BOUNCING_BALL, sizeof(LEDMATRIX_ANIMATION_BOUNCING_BALL)); return true;
      case 0x09: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_BUG, sizeof(LEDMATRIX_ANIMATION_BUG)); return true;
      case 0x0A: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_CHECK, sizeof(LEDMATRIX_ANIMATION_CHECK)); return true;
      case 0x0B: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_CLOUD, sizeof(LEDMATRIX_ANIMATION_CLOUD)); return true;
      case 0x0C: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_DOWNLOAD, sizeof(LEDMATRIX_ANIMATION_DOWNLOAD)); return true;
      case 0x0D: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_DVD, sizeof(LEDMATRIX_ANIMATION_DVD)); return true;
      case 0x0E: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_HEARTBEAT_LINE, sizeof(LEDMATRIX_ANIMATION_HEARTBEAT_LINE)); return true;
      case 0x0F: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_HEARTBEAT, sizeof(LEDMATRIX_ANIMATION_HEARTBEAT)); return true;
      case 0x10: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_INFINITY_LOOP_LOADER, sizeof(LEDMATRIX_ANIMATION_INFINITY_LOOP_LOADER)); return true;
      case 0x11: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_LOAD_CLOCK, sizeof(LEDMATRIX_ANIMATION_LOAD_CLOCK)); return true;
      case 0x12: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_LOAD, sizeof(LEDMATRIX_ANIMATION_LOAD)); return true;
      case 0x13: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_LOCK, sizeof(LEDMATRIX_ANIMATION_LOCK)); return true;
      case 0x14: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_NOTIFICATION, sizeof(LEDMATRIX_ANIMATION_NOTIFICATION)); return true;
      case 0x15: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_OPENSOURCE, sizeof(LEDMATRIX_ANIMATION_OPENSOURCE)); return true;
      case 0x16: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_SPINNING_COIN, sizeof(LEDMATRIX_ANIMATION_SPINNING_COIN)); return true;
      case 0x17: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_TETRIS, sizeof(LEDMATRIX_ANIMATION_TETRIS)); return true;
      case 0x18: g_matrix->loadWrapper(LEDMATRIX_ANIMATION_WIFI_SEARCH, sizeof(LEDMATRIX_ANIMATION_WIFI_SEARCH)); return true;
      default: return false;
    }
  }
#endif

// Main command handler - dispatches to specific command handlers
bool matrix_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
  #ifdef ARDUINO_UNOR4_WIFI
    bool handled = false;
    switch (cmd) {
      case 0x0060:  // CMD_UNO_R4_MATRIX_CREATE
        handled = matrix_create(payload, len);
        break;
      case 0x0061:  // CMD_UNO_R4_MATRIX_CLEAR
        handled = matrix_clear(payload, len);
        break;
      case 0x0062:  // CMD_UNO_R4_MATRIX_SET_PIXEL
        handled = matrix_set_pixel(payload, len);
        break;
      case 0x0063:  // CMD_UNO_R4_MATRIX_WRITE_TEXT
        handled = matrix_write_text(payload, len);
        break;
      case 0x0064:  // CMD_UNO_R4_MATRIX_ANIMATION
        handled = matrix_animation(payload, len);
        break;
      case 0x0065:  // CMD_UNO_R4_MATRIX_SET_ANIMATION_FRAME
        handled = matrix_set_animation_frame(payload, len);
        break;
      case 0x0066:  // CMD_UNO_R4_MATRIX_SET_CUSTOM_FRAME
        handled = matrix_set_custom_frame(payload, len);
        break;
      case 0x0067:  // CMD_UNO_R4_MATRIX_SHOW_CUSTOM_FRAME
        handled = matrix_show_custom_frame(payload, len);
        break;
      case 0x0068:  // CMD_UNO_R4_MATRIX_SET_CUSTOM_ANIMATION
        handled = matrix_set_custom_animation(payload, len);
        break;
      case 0x0069:  // CMD_UNO_R4_MATRIX_SHOW_CUSTOM_ANIMATION
        handled = matrix_show_custom_animation(payload, len);
        break;
      case 0x006A:  // CMD_UNO_R4_MATRIX_WRITE_BITMAP_DIRECT
        handled = matrix_write_bitmap_direct(payload, len);
        break;
      default:
        cmd_send_error();
        return false;
    }

    if (handled) {
      cmd_send_ok();
    } else {
      cmd_send_error();
    }
    return handled;
  #else
    cmd_send_error();
    return false;
  #endif
}

void matrix_init() {
  #ifdef ARDUINO_UNOR4_WIFI
    if (!g_matrix) {
      g_matrix = new ArduinoLEDMatrix();
      memset(g_animation_frames, 0, sizeof(g_animation_frames));
      memset(g_animation_frame_valid, 0, sizeof(g_animation_frame_valid));
      memset(g_pixel_buffer, 0, sizeof(g_pixel_buffer));
      
      // Initialize custom frame/animation storage
      memset(g_custom_frames, 0, sizeof(g_custom_frames));
      memset(g_custom_frame_valid, 0, sizeof(g_custom_frame_valid));
      memset(g_custom_animations, 0, sizeof(g_custom_animations));
      g_current_animation_id = 0xFF;
      g_current_frame_idx = 0;
      g_last_frame_time = 0;
      g_frame_delay_ms = 100;
    }
  #endif
}

bool matrix_update() {
  // Update custom animations (advance frames based on timing)
  // If updateing an animation, return true. Otherwise return false to indicate no update needed.
  // This allows to not throttle the main loop when animation is playing.
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_current_animation_id != 0xFF) {
      // An animation is playing
      CustomAnimation* anim = &g_custom_animations[g_current_animation_id];
      
      if (anim->valid && anim->num_frames > 0) {
        uint32_t now = millis();
        if (now - g_last_frame_time >= g_frame_delay_ms) {
          // Advance to next frame
          g_current_frame_idx++;
          
          if (g_current_frame_idx >= anim->num_frames) {
            if (anim->loop) {
              g_current_frame_idx = 0;  // loop back
            } else {
              g_current_animation_id = 0xFF;  // stop animation
              return false;
            }
          }
          
          // Display the current frame
          packed12_to_pixels(anim->frames[g_current_frame_idx], g_pixel_buffer);
          load_pixels_to_matrix();
          g_last_frame_time = now;
          return true;  // indicate that we updated the frame
        }
      }
    }
  #endif
  return false;
}

bool matrix_create(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_CREATE: initialize the matrix
  // payload: empty
  #ifdef ARDUINO_UNOR4_WIFI
    matrix_init();
    if (g_matrix) {
      if (!g_matrix->begin()) {
        return false;
      }
      memset(g_pixel_buffer, 0, sizeof(g_pixel_buffer));
      g_matrix->clear();
      return true;
    }
  #endif
  return false;
}

bool matrix_clear(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_CLEAR: clear display (all LEDs off) and stop any animation
  // payload: empty
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix) {
      memset(g_pixel_buffer, 0, sizeof(g_pixel_buffer));
      load_pixels_to_matrix();
      // Stop any active animation
      g_current_animation_id = 0xFF;
      g_current_frame_idx = 0;
      return true;
    }
  #endif
  return false;
}

bool matrix_set_pixel(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SET_PIXEL: set a single pixel
  // payload: (x[1], y[1], value[1])
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 3) {
      uint8_t x = payload[0];
      uint8_t y = payload[1];
      uint8_t value = payload[2];
      
      if (x < 12 && y < 8) {
        g_pixel_buffer[pixel_index(x, y)] = value ? 1 : 0;
        load_pixels_to_matrix();
        return true;
      }
    }
  #endif
  return false;
}

bool matrix_write_text(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_WRITE_TEXT: write text
  // payload: (speed[1], text_bytes[...])
  // speed=0 means static display
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 1) {
      uint8_t speed = payload[0];
      const char* text = (const char*)(payload + 1);
      uint16_t text_len = len - 1;

      if (text_len == 0) {
        return matrix_clear(nullptr, 0);
      }

      char temp_text[128];
      uint16_t copy_len = text_len < (sizeof(temp_text) - 1) ? text_len : (sizeof(temp_text) - 1);
      memcpy(temp_text, text, copy_len);
      temp_text[copy_len] = '\0';

      #ifdef MATRIX_WITH_ARDUINOGRAPHICS
        g_matrix->beginDraw();
        g_matrix->stroke(0xFFFFFFFF);
        g_matrix->textFont(Font_5x7);

        if (speed > 0) {
          g_matrix->textScrollSpeed(speed);
          g_matrix->beginText(0, 1, 0xFFFFFF);
          g_matrix->println(temp_text);
          g_matrix->endText(SCROLL_LEFT);
        } else {
          g_matrix->beginText(0, 1, 0xFFFFFF);
          g_matrix->println(temp_text);
          g_matrix->endText();
        }

        g_matrix->endDraw();
        return true;
      #else
        // Fallback when ArduinoGraphics support is unavailable
        memset(g_pixel_buffer, 0, sizeof(g_pixel_buffer));
        g_pixel_buffer[0] = 1;
        g_pixel_buffer[1] = 1;
        g_pixel_buffer[12] = 1;
        g_pixel_buffer[13] = 1;
        load_pixels_to_matrix();
        return true;
      #endif
    }
  #endif
  return false;
}

bool matrix_animation(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_ANIMATION: start or stop animation
  // payload: (start_stop[1], speed[1], animation_id[1])
  // start_stop: 1=play, 0=stop
  // speed: 0-255
  // animation_id: which animation to load (if starting)
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 3) {
      uint8_t start_stop = payload[0];
      uint8_t speed = payload[1];
      uint8_t animation_id = payload[2];
      
      if (start_stop == 1) {
        (void)speed; // TODO: apply speed scaling to animation timings

        if (load_builtin_animation(animation_id)) {
          g_matrix->play(true);
          return true;
        }

        // Fallback: display custom frame by id
        if (load_custom_frame_by_id(animation_id)) {
          return true;
        }
      } else {
        // Try to show frame (custom first, then built-in)
        // Check custom frames first to allow overriding built-in frames
        if (load_custom_frame_by_id(animation_id)) {
          return true;
        }
        if (load_builtin_frame(animation_id)) {
          return true;
        }
        
        // If no frame found and animation_id is 0, clear the display
        if (animation_id == 0) {
          return matrix_clear(nullptr, 0);
        }
        return false;
      }
    }
  #endif
  return false;
}

bool matrix_set_animation_frame(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SET_ANIMATION_FRAME: set custom animation frame
  // payload: (frame_number[1], led_data_as_xyz_tuples[...])
  // led_data format: x[1], y[1], v[1], repeat for each LED
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 1) {
      uint8_t frame_number = payload[0];
      
      // Clear the frame buffer first
      memset(g_animation_frames[frame_number], 0, 12);
      
      // Parse LED data and build frame
      uint8_t frame_data[12] = {0};
      for (uint16_t i = 1; i + 2 < len; i += 3) {
        uint8_t x = payload[i];
        uint8_t y = payload[i + 1];
        uint8_t value = payload[i + 2];
        
        if (x < 12 && y < 8 && value) {
          // Set the bit for this LED
          // Frame is organized as: 8 rows x 12 columns (96 bits total)
          // Packed into 3 x 32-bit integers (little-endian)
          uint16_t bit_pos = y * 12 + x;
          uint8_t byte_idx = bit_pos / 8;
          uint8_t bit_idx = bit_pos % 8;
          if (byte_idx < 12) {
            frame_data[byte_idx] |= (1 << bit_idx);
          }
        }
      }
      
      // Copy frame data to global buffer
      memcpy(g_animation_frames[frame_number], frame_data, 12);
      g_animation_frame_valid[frame_number] = true;
      
      // If this is frame 0 and no animation is currently playing,
      // load it immediately
      if (frame_number == 0) {
        packed12_to_pixels(frame_data, g_pixel_buffer);
        load_pixels_to_matrix();
      }
      
      return true;
    }
  #endif
  return false;
}

// ============================================================================
// Custom frame/animation handlers (new commands)
// ============================================================================

bool matrix_set_custom_frame(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SET_CUSTOM_FRAME: set custom frame (0-15, reduced for memory)
  // payload: (frame_id[1], led_data_as_xyz_tuples[...])
  // led_data format: x[1], y[1], v[1], repeat for each LED
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 1) {
      uint8_t frame_id = payload[0];
      
      if (frame_id >= MAX_CUSTOM_FRAMES) {
        return false;  // invalid frame ID
      }
      
      // Clear the frame buffer first
      memset(g_custom_frames[frame_id], 0, 12);
      
      // Parse LED data and build frame
      uint8_t frame_data[12] = {0};
      for (uint16_t i = 1; i + 2 < len; i += 3) {
        uint8_t x = payload[i];
        uint8_t y = payload[i + 1];
        uint8_t value = payload[i + 2];
        
        if (x < 12 && y < 8 && value) {
          uint16_t bit_pos = y * 12 + x;
          uint8_t byte_idx = bit_pos / 8;
          uint8_t bit_idx = bit_pos % 8;
          if (byte_idx < 12) {
            frame_data[byte_idx] |= (1 << bit_idx);
          }
        }
      }
      
      // Copy frame data to global buffer
      memcpy(g_custom_frames[frame_id], frame_data, 12);
      g_custom_frame_valid[frame_id] = true;
      
      return true;
    }
  #endif
  return false;
}

bool matrix_show_custom_frame(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SHOW_CUSTOM_FRAME: show custom frame (0-15, reduced for memory)
  // payload: (frame_id[1])
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 1) {
      uint8_t frame_id = payload[0];
      
      if (frame_id >= MAX_CUSTOM_FRAMES || !g_custom_frame_valid[frame_id]) {
        return false;  // invalid or unset frame
      }
      
      // Stop any custom animation
      g_current_animation_id = 0xFF;
      
      // Load and display the frame
      packed12_to_pixels(g_custom_frames[frame_id], g_pixel_buffer);
      load_pixels_to_matrix();
      
      return true;
    }
  #endif
  return false;
}

bool matrix_set_custom_animation(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SET_CUSTOM_ANIMATION: set custom animation (0-3)
  // payload: (animation_id[1], num_frames[1], loop[1], frame_data[...])
  // frame_data: num_frames * 12-byte bitmaps (packed format)
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 3) {
      uint8_t animation_id = payload[0];
      uint8_t num_frames = payload[1];
      uint8_t loop = payload[2];
      
      if (animation_id >= MAX_CUSTOM_ANIMATIONS) {
        return false;  // invalid animation ID
      }
      
      if (num_frames == 0 || num_frames > MAX_FRAMES_PER_ANIMATION) {
        return false;  // invalid frame count
      }
      
      // Check payload size
      uint16_t expected_len = 3 + (num_frames * 12);
      if (len < expected_len) {
        return false;  // not enough data
      }
      
      // Store animation data
      g_custom_animations[animation_id].num_frames = num_frames;
      g_custom_animations[animation_id].loop = (loop != 0);
      g_custom_animations[animation_id].valid = true;
      
      // Copy frame data (12 bytes per frame, packed format)
      for (uint8_t i = 0; i < num_frames; i++) {
        memcpy(g_custom_animations[animation_id].frames[i], 
               &payload[3 + i * 12], 
               12);
      }
      
      return true;
    }
  #endif
  return false;
}

bool matrix_show_custom_animation(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_SHOW_CUSTOM_ANIMATION: play custom animation (0-3)
  // payload: (animation_id[1], speed[1])
  // speed: frame delay in units of 10ms (e.g., speed=10 means 100ms per frame)
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix && len >= 2) {
      uint8_t animation_id = payload[0];
      uint8_t speed = payload[1];
      
      if (animation_id >= MAX_CUSTOM_ANIMATIONS || !g_custom_animations[animation_id].valid) {
        return false;  // invalid or unset animation
      }
      
      // Set animation state
      g_current_animation_id = animation_id;
      g_current_frame_idx = 0;
      g_last_frame_time = millis();
      g_frame_delay_ms = speed * 10;  // convert speed units to ms
      
      // Show first frame immediately
      packed12_to_pixels(g_custom_animations[animation_id].frames[0], g_pixel_buffer);
      load_pixels_to_matrix();
      
      return true;
    }
  #endif
  return false;
}

bool matrix_write_bitmap_direct(const uint8_t *payload, uint16_t len) {
  // CMD_UNO_R4_MATRIX_WRITE_BITMAP_DIRECT: write bitmap directly (no storage)
  // payload: (led_data_as_xyz_tuples[...])
  // led_data format: x[1], y[1], v[1], repeat for each LED
  #ifdef ARDUINO_UNOR4_WIFI
    if (g_matrix) {
      // Stop any custom animation
      g_current_animation_id = 0xFF;
      
      // Clear pixel buffer first
      memset(g_pixel_buffer, 0, sizeof(g_pixel_buffer));
      
      // Parse LED data and set pixels
      for (uint16_t i = 0; i + 2 < len; i += 3) {
        uint8_t x = payload[i];
        uint8_t y = payload[i + 1];
        uint8_t value = payload[i + 2];
        
        if (x < 12 && y < 8) {
          g_pixel_buffer[pixel_index(x, y)] = value ? 1 : 0;
        }
      }
      
      load_pixels_to_matrix();
      return true;
    }
  #endif
  return false;
}
