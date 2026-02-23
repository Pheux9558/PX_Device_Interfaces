#include "debug.h"
#include "modules.h"
#include <Arduino.h>

#if defined(DEBUG)

// Determine LED control method based on build flags
#if defined(DEBUG_FASTLED_DATA_PIN) || defined(DEBUG_FASTLED_TYPE) || defined(DEBUG_FASTLED_CLOCK_PIN)
    #if !defined(FASTLED_SUPPORT)
        #error "DEBUG FastLED heartbeat requires FASTLED_SUPPORT. Add -DFASTLED_SUPPORT or remove DEBUG_FASTLED_* flags."
    #endif
    #if !defined(DEBUG_FASTLED_DATA_PIN) || !defined(DEBUG_FASTLED_TYPE)
        #error "Define DEBUG_FASTLED_DATA_PIN and DEBUG_FASTLED_TYPE to enable FastLED heartbeat."
    #endif
    #define DEBUG_USE_FASTLED 1
    #define DEBUG_FASTLED_DATA_PIN_VAL DEBUG_FASTLED_DATA_PIN
    #if defined(DEBUG_FASTLED_CLOCK_PIN)
        #define DEBUG_FASTLED_CLOCK_PIN_VAL DEBUG_FASTLED_CLOCK_PIN
    #else
        #define DEBUG_FASTLED_CLOCK_PIN_VAL 0xFFFF
    #endif
    #define DEBUG_FASTLED_TYPE_VAL DEBUG_FASTLED_TYPE
#else
    // Default: use GPIO pin
    #define DEBUG_USE_GPIO 1
#endif

#if defined(DEBUG_USE_FASTLED)
    #include "fastled.h"
#endif

// Configuration for GPIO LED
#if defined(DEBUG_USE_GPIO)
    #if defined(DEBUG_LED_PIN)
        static const int LED_PIN = DEBUG_LED_PIN;
    #elif defined(LED_BUILTIN)
        static const int LED_PIN = LED_BUILTIN;
    #else
        #warning "No LED_BUILTIN defined for this board. Debug heartbeat will be disabled. Define DEBUG_LED_PIN to enable."
        static const int LED_PIN = -1; // disabled
    #endif
#endif

static const uint32_t HEARTBEAT_INTERVAL_MS = 20; // 20 ms per state change minmal for visible color cycling without being too fast

// State variables
static uint32_t last_heartbeat_millis = 0;
static uint8_t heartbeat_state = 0; // For GPIO: 0/1, For FastLED: RGB color cycle index

#if defined(DEBUG_USE_GPIO) && defined(ARDUINO_ARCH_ESP32)
static const uint8_t DEBUG_PWM_CHANNEL = 0;
static const uint32_t DEBUG_PWM_FREQ_HZ = 5000;
static const uint8_t DEBUG_PWM_RESOLUTION = 8;
static bool debug_pwm_ready = false;
#endif

#if defined(DEBUG_BRIGHTNESS)
static const uint8_t DEBUG_BRIGHTNESS_VAL = (DEBUG_BRIGHTNESS > 255) ? 255 : DEBUG_BRIGHTNESS;
#else
static const uint8_t DEBUG_BRIGHTNESS_VAL = 255;
#endif

#if defined(DEBUG_LED_ACTIVE_LOW)
static const bool DEBUG_LED_ACTIVE_LOW_VAL = true;
#else
static const bool DEBUG_LED_ACTIVE_LOW_VAL = false;
#endif

#if defined(DEBUG_USE_GPIO)
static inline uint8_t debug_pwm_duty(uint8_t duty) {
    return DEBUG_LED_ACTIVE_LOW_VAL ? (uint8_t)(255 - duty) : duty;
}

static inline void debug_gpio_write_digital(bool on) {
    if (DEBUG_LED_ACTIVE_LOW_VAL) {
        digitalWrite(LED_PIN, on ? LOW : HIGH);
    } else {
        digitalWrite(LED_PIN, on ? HIGH : LOW);
    }
}
#endif


#if defined(DEBUG_USE_FASTLED)
static const uint16_t DEBUG_FASTLED_INSTANCE_ID = 0xFFF0; // reserved ID for debug
static bool fastled_ready = false;
#endif


const char *debug_module_flags() {
    return "DEBUG";
}

void debug_init() {
    // Register DEBUG flag in modules system
    modules_add_flag(debug_module_flags());

#if defined(DEBUG_USE_GPIO)
    // Configure GPIO LED pin as output
    if (LED_PIN >= 0) {
    #if defined(ARDUINO_ARCH_ESP32)
        // Use LEDC PWM on ESP32 so brightness works on PWM-capable pins.
        if (ledcSetup(DEBUG_PWM_CHANNEL, DEBUG_PWM_FREQ_HZ, DEBUG_PWM_RESOLUTION) > 0) {
            ledcAttachPin(LED_PIN, DEBUG_PWM_CHANNEL);
            ledcWrite(DEBUG_PWM_CHANNEL, debug_pwm_duty(0));
            debug_pwm_ready = true;
        } else {
            pinMode(LED_PIN, OUTPUT);
            debug_gpio_write_digital(false);
        }
    #else
        pinMode(LED_PIN, OUTPUT);
        debug_gpio_write_digital(false);
    #endif
    }
#elif defined(DEBUG_USE_FASTLED)
    // Initialize FastLED instance for debug LED
    if (fastled_create_debug_instance(
            DEBUG_FASTLED_INSTANCE_ID,
            DEBUG_FASTLED_DATA_PIN_VAL,
            DEBUG_FASTLED_CLOCK_PIN_VAL,
            DEBUG_FASTLED_TYPE_VAL)) {
        fastled_ready = true;
    }
#endif

    last_heartbeat_millis = millis();
}

void debug_heartbeat() {
    uint32_t now = millis();
    
    // Check if it's time for next heartbeat state change
    if ((now - last_heartbeat_millis) < HEARTBEAT_INTERVAL_MS) {
        return; // not time yet, return immediately (non-blocking)
    }
    
    last_heartbeat_millis = now;
    
#if defined(DEBUG_USE_GPIO)
    // Toggle GPIO LED
    if (LED_PIN >= 0) {
        if (DEBUG_BRIGHTNESS_VAL == 0) {
        #if defined(ARDUINO_ARCH_ESP32)
            if (debug_pwm_ready) {
                ledcWrite(DEBUG_PWM_CHANNEL, debug_pwm_duty(0));
            } else {
                debug_gpio_write_digital(false);
            }
        #else
            analogWrite(LED_PIN, debug_pwm_duty(0));
        #endif
        } else {
            heartbeat_state = !heartbeat_state;
            uint8_t duty = heartbeat_state ? DEBUG_BRIGHTNESS_VAL : 0;
        #if defined(ARDUINO_ARCH_ESP32)
            if (debug_pwm_ready) {
                ledcWrite(DEBUG_PWM_CHANNEL, debug_pwm_duty(duty));
            } else {
                debug_gpio_write_digital(heartbeat_state);
            }
        #else
            analogWrite(LED_PIN, debug_pwm_duty(duty));
        #endif
        }
    }
    
#elif defined(DEBUG_USE_FASTLED)
    // Cycle through RGB colors
    if (fastled_ready) {
        // Increment to next color: R(0) -> G(1) -> B(2) -> R(0) ...
        heartbeat_state = (heartbeat_state + 1) % 3;
        
        // Set color based on state
        uint8_t r = (heartbeat_state == 0) ? 255 : 0;
        uint8_t g = (heartbeat_state == 1) ? 255 : 0;
        uint8_t b = (heartbeat_state == 2) ? 255 : 0;

        if (DEBUG_BRIGHTNESS_VAL < 255) {
            // Scale color channels by brightness 0-255
            r = (uint8_t)((uint16_t)r * DEBUG_BRIGHTNESS_VAL / 255);
            g = (uint8_t)((uint16_t)g * DEBUG_BRIGHTNESS_VAL / 255);
            b = (uint8_t)((uint16_t)b * DEBUG_BRIGHTNESS_VAL / 255);
        }
        
        fastled_set_single_led(DEBUG_FASTLED_INSTANCE_ID, r, g, b);
    }
#endif
}

#else // !defined(DEBUG)

// Stub implementations when DEBUG is not defined
const char *debug_module_flags() {
    return "";
}

void debug_init() {
    // Do nothing when DEBUG not defined
}

void debug_heartbeat() {
    // Do nothing when DEBUG not defined
}

#endif // DEBUG
