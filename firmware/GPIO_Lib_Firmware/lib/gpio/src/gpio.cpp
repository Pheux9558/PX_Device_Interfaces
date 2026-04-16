// GPIO RTOS Service - Phase 3 Task Implementation
// Timer-driven polling of digital and analog inputs using rtosal_delay_until()
// All GPIO state owned by GpioTask
#include "gpio.h"
#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"
#include "../../rtosal/src/rtosal.h"
#include <string.h>
#include <stdio.h>

#if defined(ARDUINO)
/* HAL replaces direct vendor calls.  ESP32 port: hal_port_esp32.cpp */
#include "../../hal/src/hal_gpio.h"

// Self-register GPIO command handler (0x00xx range) with the dispatch system.
// Replaces the manual cmd_register_handler() calls that were previously in
// gpio_init() and in main.cpp.  Processed by cmd_init() -> cmd_auto_register_all().
CMD_REGISTER(0x0000, 0x001F, gpio_cmd_handler)

// GPIO state structures (owned by task)
#define MAX_DIGITAL_INPUTS 16
#define MAX_ANALOG_INPUTS 8
#define GPIO_POLL_INTERVAL_MS 10

typedef struct {
    uint16_t pin;
    uint8_t last;
    volatile bool dirty;
    bool used;
    bool use_interrupt;
} digital_input_t;

typedef struct {
    uint16_t pin;
    uint16_t last;
    uint16_t threshold;
    bool used;
    bool initialized;
} analog_input_t;

// All GPIO service state bundled into one struct — owned by GpioTask.
// The task is created with &g_gpio_state as its arg so ownership is explicit.
// The mutex serialises competing accesses from DispatchTask (cmd handler) and GpioTask (poll loop).
typedef struct {
    digital_input_t digital_inputs[MAX_DIGITAL_INPUTS];
    analog_input_t  analog_inputs[MAX_ANALOG_INPUTS];
    uint16_t        analog_default_threshold;
} gpio_state_t;

static gpio_state_t   g_gpio_state;
static rtosal_mutex_t g_gpio_mutex = NULL;
static rtosal_task_t  g_gpio_task  = NULL;

// Forward declarations
static void gpio_task_fn(void *arg);
static void _call_dbg(const char *msg);

// Debug callback (optional)
static void (*g_debug_cb)(const char *msg) = NULL;
void gpio_set_debug_cb(void (*cb)(const char *msg)) { g_debug_cb = cb; }

static void _call_dbg(const char *msg) {
    if (g_debug_cb) {
        g_debug_cb(msg);
    }
}

// Helper: Find digital input by pin
static digital_input_t *find_digital_input(gpio_state_t *s, uint16_t pin) {
    for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
        if (s->digital_inputs[i].used && s->digital_inputs[i].pin == pin)
            return &s->digital_inputs[i];
    }
    return NULL;
}

// Helper: Allocate digital input slot
static digital_input_t *alloc_digital_input(gpio_state_t *s, uint16_t pin) {
    for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
        if (!s->digital_inputs[i].used) {
            s->digital_inputs[i].used          = true;
            s->digital_inputs[i].pin           = pin;
            s->digital_inputs[i].last          = 0;
            s->digital_inputs[i].dirty         = true;
            s->digital_inputs[i].use_interrupt = false;
            return &s->digital_inputs[i];
        }
    }
    return NULL;
}

// Helper: Find analog input by pin
static analog_input_t *find_analog_input(gpio_state_t *s, uint16_t pin) {
    for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
        if (s->analog_inputs[i].used && s->analog_inputs[i].pin == pin)
            return &s->analog_inputs[i];
    }
    return NULL;
}

// Helper: Allocate analog input slot
static analog_input_t *alloc_analog_input(gpio_state_t *s, uint16_t pin) {
    for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
        if (!s->analog_inputs[i].used) {
            s->analog_inputs[i].used         = true;
            s->analog_inputs[i].pin          = pin;
            s->analog_inputs[i].last         = 0;
            s->analog_inputs[i].threshold    = s->analog_default_threshold;
            s->analog_inputs[i].initialized  = false;
            return &s->analog_inputs[i];
        }
    }
    return NULL;
}

// Hardware abstraction: digital operations
static void gpio_digital_write(uint16_t pin, uint8_t value) {
    hal_gpio_write(pin, value);
    char b[64];
    snprintf(b, sizeof(b), "gpio: digital_write pin=%u val=%u", (unsigned)pin, (unsigned)value);
    _call_dbg(b);
}

static int gpio_digital_read(uint16_t pin) {
    uint8_t v = 0;
    hal_gpio_read(pin, &v);
    if (g_debug_cb) {
        char b[64];
        snprintf(b, sizeof(b), "gpio: digital_read pin=%u val=%u", (unsigned)pin, (unsigned)(v & 1u));
        _call_dbg(b);
    }
    return (int)(v & 1u);
}

// Hardware abstraction: analog operations
static void gpio_analog_write(uint16_t pin, uint16_t value) {
    hal_gpio_analog_write(pin, value);
    char b[64];
    snprintf(b, sizeof(b), "gpio: analog_write pin=%u val=%u", (unsigned)pin, (unsigned)value);
    _call_dbg(b);
}

static int gpio_analog_read(uint16_t pin) {
    uint16_t v = 0;
    hal_gpio_analog_read(pin, &v);
    if (g_debug_cb) {
        char b[64];
        snprintf(b, sizeof(b), "gpio: analog_read pin=%u val=%u", (unsigned)pin, (unsigned)v);
        _call_dbg(b);
    }
    return (int)v;
}

// Helper: Send digital input change notification to host
static void gpio_send_digital_update(uint16_t pin, uint8_t value) {
    uint8_t resp[2];
    resp[0] = (uint8_t)(pin & 0xFF);
    resp[1] = value & 0xFF;
    cmd_send_response(0x0010, resp, 2);
}

// Helper: Send analog input change notification to host  
static void gpio_send_analog_update(uint16_t pin, uint16_t value) {
    uint8_t resp[3];
    resp[0] = (uint8_t)(pin & 0xFF);
    resp[1] = (uint8_t)(value & 0xFF);
    resp[2] = (uint8_t)((value >> 8) & 0xFF);
    cmd_send_response(0x0012, resp, 3);
}

// Helper: Configure pin mode
static void gpio_set_mode(uint16_t pin, uint8_t mode) {
    if (mode) {
        hal_gpio_mode(pin, HAL_GPIO_MODE_OUTPUT);
        char b[64];
        snprintf(b, sizeof(b), "gpio: set pin %u MODE=OUTPUT", (unsigned)pin);
        _call_dbg(b);
    } else {
        hal_gpio_mode(pin, HAL_GPIO_MODE_INPUT);
        char b[64];
        snprintf(b, sizeof(b), "gpio: set pin %u MODE=INPUT", (unsigned)pin);
        _call_dbg(b);
    }
}

// Helper: Configure pin pull resistor
static void gpio_set_pull(uint16_t pin, uint8_t pull) {
    if (pull == 1) {
        // pull-up
        hal_gpio_mode(pin, HAL_GPIO_MODE_INPUT_PULLUP);
        char b[64];
        snprintf(b, sizeof(b), "gpio: set pin %u PULL=UP", (unsigned)pin);
        _call_dbg(b);
    } else if (pull == 2) {
        hal_gpio_mode(pin, HAL_GPIO_MODE_INPUT_PULLDOWN);
        char b[64];
        snprintf(b, sizeof(b), "gpio: set pin %u PULL=DOWN", (unsigned)pin);
        _call_dbg(b);
    } else {
        hal_gpio_mode(pin, HAL_GPIO_MODE_INPUT);
        char b[64];
        snprintf(b, sizeof(b), "gpio: set pin %u PULL=NONE", (unsigned)pin);
        _call_dbg(b);
    }
}

// ISR helper — platform-agnostic; IRAM handling is in the ESP32 HAL port trampoline.
static void gpio_digital_isr(void *arg) {
    digital_input_t *entry = (digital_input_t *)arg;
    if (entry) {
        entry->dirty = true;
    }
}

static void gpio_attach_interrupt(digital_input_t *entry) {
    if (!entry) return;
    hal_gpio_attach_isr(entry->pin, gpio_digital_isr, entry, HAL_GPIO_ISR_CHANGE);
    entry->use_interrupt = true;
}

static void gpio_poll_inputs_once(gpio_state_t *s) {
    if (!s) return;

    // Poll digital inputs
    for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
        digital_input_t *entry = &s->digital_inputs[i];
        if (!entry->used) continue;
        int v = gpio_digital_read(entry->pin);
        if ((uint8_t)v != entry->last) {
            entry->last = (uint8_t)v;
            gpio_send_digital_update(entry->pin, entry->last);
        }
        entry->dirty = false;
    }

    // Poll analog inputs
    for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
        analog_input_t *entry = &s->analog_inputs[i];
        if (!entry->used) continue;

        int v = gpio_analog_read(entry->pin);
        if (!entry->initialized) {
            entry->last = (uint16_t)v;
            entry->initialized = true;
            gpio_send_analog_update(entry->pin, entry->last);
            continue;
        }

        int diff = abs((int)entry->last - v);
        if (diff >= (int)entry->threshold) {
            entry->last = (uint16_t)v;
            gpio_send_analog_update(entry->pin, entry->last);
        }
    }
}

// Register digital input and send initial state to host
static digital_input_t *gpio_register_digital_input(gpio_state_t *s, uint16_t pin) {
    digital_input_t *entry = find_digital_input(s, pin);
    if (!entry) entry = alloc_digital_input(s, pin);
    if (!entry) return NULL;
    int v = gpio_digital_read(pin);
    entry->last = (uint8_t)(v & 0xFF);
    entry->dirty = false;
    gpio_attach_interrupt(entry);
    gpio_send_digital_update(pin, entry->last);
    return entry;
}

// Register analog input and send initial state to host
static analog_input_t *gpio_register_analog_input(gpio_state_t *s, uint16_t pin) {
    analog_input_t *entry = find_analog_input(s, pin);
    if (!entry) entry = alloc_analog_input(s, pin);
    if (!entry) return NULL;
    int v = gpio_analog_read(pin);
    entry->last = (uint16_t)v;
    entry->initialized = true;
    gpio_send_analog_update(pin, entry->last);
    return entry;
}

// GpioTask main loop: timer-driven polling with rtosal_delay_until()
// The task arg is a pointer to gpio_state_t — the task is the sole owner of that state.
static void gpio_task_fn(void *arg) {
    gpio_state_t *s = (gpio_state_t *)arg;

    // Initialise state (task is sole writer at this point — mutex not needed yet)
    for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
        s->digital_inputs[i].used          = false;
        s->digital_inputs[i].dirty         = false;
        s->digital_inputs[i].use_interrupt = false;
    }
    for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
        s->analog_inputs[i].used        = false;
        s->analog_inputs[i].initialized = false;
        s->analog_inputs[i].threshold   = s->analog_default_threshold;
    }

    modules_add_flag("GPIO");

    // Task loop: scan for input changes at fixed 10ms interval
    rtosal_tick_t wake_time = rtosal_now_ticks();

    while (1) {
        // Lock while reading/writing shared state (cmd handler may run concurrently)
        rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);

        gpio_poll_inputs_once(s);

        rtosal_mutex_unlock(g_gpio_mutex);

        // Sleep until next poll interval
        rtosal_delay_until(&wake_time, GPIO_POLL_INTERVAL_MS);
    }
}

// Command handler: process GPIO commands (0x00xx range).
// Runs on DispatchTask — acquires g_gpio_mutex before touching shared state.
bool gpio_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    gpio_state_t *s = &g_gpio_state;
    switch (cmd) {
        case 0x0000: // digital output (setup)
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_mode(pin, 1);
            }
            cmd_send_ok();
            return true;

        case 0x0001: // digital input (setup)
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_mode(pin, 0);
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                gpio_register_digital_input(s, pin);
                rtosal_mutex_unlock(g_gpio_mutex);
            }
            cmd_send_ok();
            return true;

        case 0x0002: // digital input pullup
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_pull(pin, 1);
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                gpio_register_digital_input(s, pin);
                rtosal_mutex_unlock(g_gpio_mutex);
            }
            cmd_send_ok();
            return true;

        case 0x0003: // digital input pulldown
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_pull(pin, 2);
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                gpio_register_digital_input(s, pin);
                rtosal_mutex_unlock(g_gpio_mutex);
            }
            cmd_send_ok();
            return true;

        case 0x0008: // analog output
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_mode(pin, 1);
            }
            cmd_send_ok();
            return true;

        case 0x0009: // analog input
            if (len >= 1) {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                gpio_set_mode(pin, 0);
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                gpio_register_analog_input(s, pin);
                rtosal_mutex_unlock(g_gpio_mutex);
            }
            cmd_send_ok();
            return true;

        case 0x000A: // analog read resolution (ADC bits)
            if (len < 1) { cmd_send_error(); return true; }
            {
                uint8_t bits = payload[0];
                hal_gpio_analog_resolution(bits);
                cmd_send_ok();
            }
            return true;

        case 0x000B: // analog tolerance / threshold
            if (len < 1) { cmd_send_error(); return true; }
            if (len == 1) {
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                s->analog_default_threshold = payload[0];
                rtosal_mutex_unlock(g_gpio_mutex);
                cmd_send_ok();
                return true;
            }
            {
                uint16_t pin = (len >= 3) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                uint8_t threshold = (len >= 3) ? payload[2] : payload[1];
                rtosal_mutex_lock(g_gpio_mutex, RTOSAL_MAX_DELAY);
                analog_input_t *entry = find_analog_input(s, pin);
                if (entry) entry->threshold = threshold;
                rtosal_mutex_unlock(g_gpio_mutex);
                if (!entry) { cmd_send_error(); return true; }
                cmd_send_ok();
                return true;
            }

        case 0x0010: // digital read
            if (len < 1) { cmd_send_error(); return true; }
            {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                int v = gpio_digital_read(pin);
                uint8_t resp[2];
                resp[0] = (uint8_t)(pin & 0xFF);
                resp[1] = (uint8_t)(v & 0xFF);
                cmd_send_response(0x0010, resp, 2);
            }
            return true;

        case 0x0011: // digital write
            if (len < 2) { cmd_send_error(); return true; }
            {
                uint16_t pin = (len >= 3) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                uint8_t val = payload[len-1];
                gpio_digital_write(pin, val);
                cmd_send_ok();
            }
            return true;

        case 0x0012: // analog read
            if (len < 1) { cmd_send_error(); return true; }
            {
                uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
                int v = gpio_analog_read(pin);
                gpio_send_analog_update(pin, (uint16_t)v);
            }
            return true;

        case 0x0013: // analog write (16-bit value)
            if (len < 3) { cmd_send_error(); return true; }
            {
                uint16_t pin, val;
                if (len >= 4) {
                    pin = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
                    val = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
                } else {
                    pin = payload[0];
                    val = (uint16_t)payload[1] | ((uint16_t)payload[2] << 8);
                }
                gpio_analog_write(pin, val);
                cmd_send_ok();
            }
            return true;

        default:
            return false;
    }
}

// Legacy polling function (compatibility wrapper, now does nothing as task handles it)
void gpio_poll_inputs() {
    // On STM32 bare-metal, rtosal_task_create() returns RTOSAL_ERROR and
    // GpioTask is never started, so we must poll cooperatively from loop().
    if (g_gpio_task != NULL) {
        return;
    }
    if (rtosal_mutex_lock(g_gpio_mutex, 0) != RTOSAL_OK) {
        return;
    }
    gpio_poll_inputs_once(&g_gpio_state);
    rtosal_mutex_unlock(g_gpio_mutex);
}

// Module info string
const char *gpio_module_flags(void) {
    return "GPIO";
}

// Initialize GPIO task
void gpio_init(void) {
    // Initialise state struct defaults before the task starts
    g_gpio_state.analog_default_threshold = 4;

    // Create mutex that serialises cmd-handler vs GpioTask access to g_gpio_state
    rtosal_mutex_create(&g_gpio_mutex);

    // Create GpioTask; pass &g_gpio_state so the task explicitly owns the state
    rtosal_task_config_t gpio_cfg = {
        .name        = "GpioTask",
        .fn          = gpio_task_fn,
        .arg         = &g_gpio_state,
        .stack_words = 8192,
        .priority    = 1
    };
    rtosal_task_create(&gpio_cfg, &g_gpio_task);
}

#endif  // ARDUINO
