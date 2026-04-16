#include "encoder.h"

#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"
#include "../../hal/src/hal_gpio.h"
#include "../../rtosal/src/rtosal.h"

#include <string.h>

#if defined(ARDUINO)
#include <Arduino.h>
#endif

#if defined(ARDUINO_ARCH_STM32)
extern "C" uint32_t HAL_GetTick(void);
#endif

#if defined(ENCODER_SUPPORT)

CMD_REGISTER(0x0310, 0x031F, encoder_cmd_handler)

#define MAX_ENCODER_INSTANCES 4
#define ENCODER_POLL_INTERVAL_MS 1
#define ENCODER_QUAD_SCALE 4

typedef struct {
    uint16_t id;
    uint16_t pin_a;
    uint16_t pin_b;
    uint16_t pin_z;
    uint16_t ppr;
    volatile int32_t position;
    volatile int32_t revolutions;
    volatile int8_t direction;
    volatile uint8_t last_ab_state;
    volatile uint8_t z_state;
    bool used;
    bool active;
    bool has_z;
    bool use_interrupts;
    bool flip;   /* when true, invert the quadrature direction */
} encoder_instance_t;

typedef struct {
    encoder_instance_t instances[MAX_ENCODER_INSTANCES];
} encoder_state_t;

static encoder_state_t g_encoder_state;
static rtosal_task_t g_encoder_task = NULL;
static rtosal_mutex_t g_encoder_mutex = NULL;
static uint32_t g_encoder_last_poll_ms = 0;
static int8_t g_encoder_edge_accumulator[MAX_ENCODER_INSTANCES] = {0};

static uint32_t encoder_now_ms(void) {
#if defined(ARDUINO_ARCH_STM32)
    return HAL_GetTick();
#else
    return (uint32_t)rtosal_now_ticks();
#endif
}

static encoder_instance_t *encoder_find(uint16_t id) {
    for (int i = 0; i < MAX_ENCODER_INSTANCES; ++i) {
        if (g_encoder_state.instances[i].used && g_encoder_state.instances[i].id == id) {
            return &g_encoder_state.instances[i];
        }
    }
    return NULL;
}

static encoder_instance_t *encoder_alloc(uint16_t id) {
    for (int i = 0; i < MAX_ENCODER_INSTANCES; ++i) {
        if (!g_encoder_state.instances[i].used) {
            memset(&g_encoder_state.instances[i], 0, sizeof(encoder_instance_t));
            g_encoder_state.instances[i].used = true;
            g_encoder_state.instances[i].id = id;
            g_encoder_state.instances[i].ppr = 1024;
            g_encoder_state.instances[i].pin_z = 0xFFFF;
            g_encoder_state.instances[i].use_interrupts = false;
            return &g_encoder_state.instances[i];
        }
    }
    return NULL;
}

static uint8_t read_ab_state(encoder_instance_t *enc) {
    uint8_t a = 0;
    uint8_t b = 0;
    hal_gpio_read(enc->pin_a, &a);
    hal_gpio_read(enc->pin_b, &b);
    return ((a & 0x01) << 1) | (b & 0x01);
}

static void encoder_step_wrapped(encoder_instance_t *enc, int8_t steps) {
    if (!enc || steps == 0 || enc->ppr == 0) {
        return;
    }
    int32_t ppr = (int32_t)enc->ppr;
    int32_t pos = enc->position;
    int32_t rev = enc->revolutions;

    int32_t next = pos + (int32_t)steps;
    while (next >= ppr) {
        next -= ppr;
        rev += 1;
    }
    while (next < 0) {
        next += ppr;
        rev -= 1;
    }

    enc->position = next;
    enc->revolutions = rev;
}

static void encoder_apply_delta(encoder_instance_t *enc, int8_t d) {
    if (!enc || d == 0) {
        return;
    }
    if (enc->flip) d = -d;

    // Decode quadrature edges at x4 internally; expose wrapped position in
    // user counts by committing one position step per 4 edge transitions.
    int idx = (int)(enc - &g_encoder_state.instances[0]);
    if (idx < 0 || idx >= MAX_ENCODER_INSTANCES) {
        return;
    }
    g_encoder_edge_accumulator[idx] += d;
    if (g_encoder_edge_accumulator[idx] >= ENCODER_QUAD_SCALE ||
        g_encoder_edge_accumulator[idx] <= -ENCODER_QUAD_SCALE) {
        int8_t q = (int8_t)(g_encoder_edge_accumulator[idx] / ENCODER_QUAD_SCALE);
        g_encoder_edge_accumulator[idx] -= (int8_t)(q * ENCODER_QUAD_SCALE);
        encoder_step_wrapped(enc, q);
    }

    enc->direction = (d > 0) ? 1 : -1;
}

static int8_t quadrature_delta(uint8_t old_state, uint8_t new_state) {
    static const int8_t table[16] = {
        0, -1, +1,  0,
        +1, 0,  0, -1,
        -1, 0,  0, +1,
        0, +1, -1,  0,
    };
    return table[((old_state & 0x03) << 2) | (new_state & 0x03)];
}

#if defined(ARDUINO)
#define MAX_ENCODER_ISR_SLOTS (MAX_ENCODER_INSTANCES * 3)
typedef struct {
    encoder_instance_t *enc;
    uint8_t channel;
    uint16_t pin;
    bool used;
} encoder_isr_slot_t;

static encoder_isr_slot_t g_encoder_isr_slots[MAX_ENCODER_ISR_SLOTS];

static void encoder_isr_dispatch(uint8_t slot_idx) {
    if (slot_idx >= MAX_ENCODER_ISR_SLOTS) {
        return;
    }
    encoder_isr_slot_t *slot = &g_encoder_isr_slots[slot_idx];
    encoder_instance_t *enc = slot->enc;
    if (!slot->used || !enc || !enc->active) {
        return;
    }

    if (slot->channel == 2 && enc->has_z) {
        uint8_t z = 0;
        hal_gpio_read(enc->pin_z, &z);
        enc->z_state = (z & 0x01);
        return;
    }

    uint8_t now_state = read_ab_state(enc);
    int8_t d = quadrature_delta(enc->last_ab_state, now_state);
    if (d != 0) {
        encoder_apply_delta(enc, d);
        enc->last_ab_state = now_state;
    }
}

#define ENC_ISR_SLOT_FN(N) static void encoder_isr_slot_##N(void) { encoder_isr_dispatch(N); }
ENC_ISR_SLOT_FN(0)  ENC_ISR_SLOT_FN(1)  ENC_ISR_SLOT_FN(2)  ENC_ISR_SLOT_FN(3)
ENC_ISR_SLOT_FN(4)  ENC_ISR_SLOT_FN(5)  ENC_ISR_SLOT_FN(6)  ENC_ISR_SLOT_FN(7)
ENC_ISR_SLOT_FN(8)  ENC_ISR_SLOT_FN(9)  ENC_ISR_SLOT_FN(10) ENC_ISR_SLOT_FN(11)

typedef void (*encoder_isr_fn_t)(void);
static const encoder_isr_fn_t g_encoder_isr_fns[MAX_ENCODER_ISR_SLOTS] = {
    encoder_isr_slot_0, encoder_isr_slot_1, encoder_isr_slot_2, encoder_isr_slot_3,
    encoder_isr_slot_4, encoder_isr_slot_5, encoder_isr_slot_6, encoder_isr_slot_7,
    encoder_isr_slot_8, encoder_isr_slot_9, encoder_isr_slot_10, encoder_isr_slot_11,
};

static int encoder_alloc_isr_slot(encoder_instance_t *enc, uint8_t channel, uint16_t pin) {
    for (int i = 0; i < MAX_ENCODER_ISR_SLOTS; ++i) {
        if (!g_encoder_isr_slots[i].used) {
            g_encoder_isr_slots[i].used = true;
            g_encoder_isr_slots[i].enc = enc;
            g_encoder_isr_slots[i].channel = channel;
            g_encoder_isr_slots[i].pin = pin;
            return i;
        }
    }
    return -1;
}

static void encoder_release_isr_slots(encoder_instance_t *enc) {
    for (int i = 0; i < MAX_ENCODER_ISR_SLOTS; ++i) {
        if (g_encoder_isr_slots[i].used && g_encoder_isr_slots[i].enc == enc) {
            detachInterrupt((uint8_t)g_encoder_isr_slots[i].pin);
            g_encoder_isr_slots[i].used = false;
            g_encoder_isr_slots[i].enc = NULL;
        }
    }
}

static bool encoder_attach_interrupts(encoder_instance_t *enc) {
    if (!enc) {
        return false;
    }

    encoder_release_isr_slots(enc);

    int slot_a = encoder_alloc_isr_slot(enc, 0, enc->pin_a);
    int slot_b = encoder_alloc_isr_slot(enc, 1, enc->pin_b);
    if (slot_a < 0 || slot_b < 0) {
        encoder_release_isr_slots(enc);
        return false;
    }

    attachInterrupt((uint8_t)enc->pin_a, g_encoder_isr_fns[slot_a], CHANGE);
    attachInterrupt((uint8_t)enc->pin_b, g_encoder_isr_fns[slot_b], CHANGE);

    if (enc->has_z) {
        int slot_z = encoder_alloc_isr_slot(enc, 2, enc->pin_z);
        if (slot_z >= 0) {
            attachInterrupt((uint8_t)enc->pin_z, g_encoder_isr_fns[slot_z], CHANGE);
        }
    }

    enc->use_interrupts = true;
    return true;
}
#endif

static void encoder_service_tick(void) {
    for (int i = 0; i < MAX_ENCODER_INSTANCES; ++i) {
        encoder_instance_t *enc = &g_encoder_state.instances[i];
        if (!enc->used || !enc->active) {
            continue;
        }

        // A/B quadrature decode is interrupt-driven when ISR attach succeeded.
        // Poll fallback remains active only when interrupts are unavailable.
        if (!enc->use_interrupts) {
            uint8_t now_state = read_ab_state(enc);
            int8_t d = quadrature_delta(enc->last_ab_state, now_state);
            if (d != 0) {
                encoder_apply_delta(enc, d);
                enc->last_ab_state = now_state;
            }
        }

        if (enc->has_z) {
            uint8_t z = 0;
            hal_gpio_read(enc->pin_z, &z);
            enc->z_state = (z & 0x01);
        }
    }
}

static void encoder_task_fn(void *arg) {
    (void)arg;
    modules_add_flag("ENCODER");

    rtosal_tick_t wake_time = rtosal_now_ticks();
    while (1) {
        rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
        encoder_service_tick();
        rtosal_mutex_unlock(g_encoder_mutex);
        rtosal_delay_until(&wake_time, ENCODER_POLL_INTERVAL_MS);
    }
}

void encoder_poll(void) {
    uint32_t now_ms = encoder_now_ms();
    if ((uint32_t)(now_ms - g_encoder_last_poll_ms) < ENCODER_POLL_INTERVAL_MS) {
        return;
    }
    g_encoder_last_poll_ms = now_ms;

    rtosal_mutex_lock(g_encoder_mutex, 0);
    encoder_service_tick();
    rtosal_mutex_unlock(g_encoder_mutex);
}

bool encoder_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    switch (cmd) {
        case 0x0310: { // CMD_ENCODER_CREATE
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) {
                enc = encoder_alloc(id);
            }
            rtosal_mutex_unlock(g_encoder_mutex);
            if (!enc) {
                cmd_send_error();
                return true;
            }
            cmd_send_ok();
            return true;
        }

        case 0x0311: { // CMD_ENCODER_SET_PINS
            if (len < 4) {
                cmd_send_error();
                return true;
            }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            uint16_t pin_a = payload[2];
            uint16_t pin_b = payload[3];
            bool has_z = (len >= 5);
            uint16_t pin_z = has_z ? payload[4] : 0xFFFF;

            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) {
                rtosal_mutex_unlock(g_encoder_mutex);
                cmd_send_error();
                return true;
            }

            enc->pin_a = pin_a;
            enc->pin_b = pin_b;
            enc->pin_z = pin_z;
            enc->has_z = has_z;

            hal_gpio_mode(pin_a, HAL_GPIO_MODE_INPUT_PULLUP);
            hal_gpio_mode(pin_b, HAL_GPIO_MODE_INPUT_PULLUP);
            if (has_z) {
                hal_gpio_mode(pin_z, HAL_GPIO_MODE_INPUT_PULLUP);
            }

            enc->last_ab_state = read_ab_state(enc);
            {
                int idx = (int)(enc - &g_encoder_state.instances[0]);
                if (idx >= 0 && idx < MAX_ENCODER_INSTANCES) {
                    g_encoder_edge_accumulator[idx] = 0;
                }
            }
#if defined(ARDUINO)
            if (!encoder_attach_interrupts(enc)) {
                enc->use_interrupts = false;
            }
#else
            enc->use_interrupts = false;
#endif
            enc->active = true;
            rtosal_mutex_unlock(g_encoder_mutex);

            cmd_send_ok();
            return true;
        }

        case 0x0312: { // CMD_ENCODER_SET_PPR
            if (len < 4) {
                cmd_send_error();
                return true;
            }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            uint16_t ppr = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
            if (ppr == 0) {
                ppr = 1;
            }

            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) {
                rtosal_mutex_unlock(g_encoder_mutex);
                cmd_send_error();
                return true;
            }
            enc->ppr = ppr;
            if (enc->position >= (int32_t)enc->ppr) {
                enc->position = 0;
            }
            {
                int idx = (int)(enc - &g_encoder_state.instances[0]);
                if (idx >= 0 && idx < MAX_ENCODER_INSTANCES) {
                    g_encoder_edge_accumulator[idx] = 0;
                }
            }
            rtosal_mutex_unlock(g_encoder_mutex);

            cmd_send_ok();
            return true;
        }

        case 0x0313: { // CMD_ENCODER_READ
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            uint8_t resp[12];
            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) {
                rtosal_mutex_unlock(g_encoder_mutex);
                cmd_send_error();
                return true;
            }
            int32_t pos;
            int32_t revs;
            int8_t dir;
            uint8_t z;
#if defined(ARDUINO)
            noInterrupts();
#endif
            pos = enc->position;
            revs = enc->revolutions;
            dir = enc->direction;
            z = enc->z_state;
#if defined(ARDUINO)
            interrupts();
#endif
            rtosal_mutex_unlock(g_encoder_mutex);

            resp[0] = (uint8_t)(id & 0xFF);
            resp[1] = (uint8_t)((id >> 8) & 0xFF);
            resp[2] = (uint8_t)(pos & 0xFF);
            resp[3] = (uint8_t)((pos >> 8) & 0xFF);
            resp[4] = (uint8_t)((pos >> 16) & 0xFF);
            resp[5] = (uint8_t)((pos >> 24) & 0xFF);
            resp[6] = (uint8_t)dir;
            resp[7] = z;
            resp[8] = (uint8_t)(revs & 0xFF);
            resp[9] = (uint8_t)((revs >> 8) & 0xFF);
            resp[10] = (uint8_t)((revs >> 16) & 0xFF);
            resp[11] = (uint8_t)((revs >> 24) & 0xFF);
            cmd_send_response(0x0313, resp, sizeof(resp));
            return true;
        }

        case 0x0315: { // CMD_ENCODER_FLIP — toggle direction inversion
            if (len < 2) { cmd_send_error(); return true; }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) { rtosal_mutex_unlock(g_encoder_mutex); cmd_send_error(); return true; }
            enc->flip = !enc->flip;
            rtosal_mutex_unlock(g_encoder_mutex);
            cmd_send_ok();
            return true;
        }

        case 0x0314: { // CMD_ENCODER_RESET
            if (len < 2) {
                cmd_send_error();
                return true;
            }
            uint16_t id = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
            rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
            encoder_instance_t *enc = encoder_find(id);
            if (!enc) {
                rtosal_mutex_unlock(g_encoder_mutex);
                cmd_send_error();
                return true;
            }

            enc->position = 0;
            enc->revolutions = 0;
            enc->direction = 0;
            enc->last_ab_state = read_ab_state(enc);

            int idx = (int)(enc - &g_encoder_state.instances[0]);
            if (idx >= 0 && idx < MAX_ENCODER_INSTANCES) {
                g_encoder_edge_accumulator[idx] = 0;
            }

            rtosal_mutex_unlock(g_encoder_mutex);
            cmd_send_ok();
            return true;
        }

        default:
            return false;
    }
}

bool encoder_get_snapshot(uint16_t enc_id,
                          int32_t *out_position,
                          int32_t *out_revolutions,
                          int8_t  *out_direction) {
#if defined(ENCODER_SUPPORT)
    rtosal_mutex_lock(g_encoder_mutex, RTOSAL_MAX_DELAY);
    encoder_instance_t *enc = encoder_find(enc_id);
    if (!enc || !enc->active) {
        rtosal_mutex_unlock(g_encoder_mutex);
        return false;
    }
#if defined(ARDUINO)
    noInterrupts();
#endif
    int32_t pos = enc->position;
    int32_t rev = enc->revolutions;
    int8_t  dir = enc->direction;
#if defined(ARDUINO)
    interrupts();
#endif
    rtosal_mutex_unlock(g_encoder_mutex);
    if (out_position)    *out_position    = pos;
    if (out_revolutions) *out_revolutions = rev;
    if (out_direction)   *out_direction   = dir;
    return true;
#else
    (void)enc_id; (void)out_position; (void)out_revolutions; (void)out_direction;
    return false;
#endif
}

void encoder_init(void) {
    memset(&g_encoder_state, 0, sizeof(g_encoder_state));
    g_encoder_last_poll_ms = encoder_now_ms();
    rtosal_mutex_create(&g_encoder_mutex);

    rtosal_task_config_t cfg = {
        .name = "EncoderTask",
        .fn = encoder_task_fn,
        .arg = &g_encoder_state,
        .stack_words = 4096,
        .priority = 1,
    };
    rtosal_task_create(&cfg, &g_encoder_task);
}

const char *encoder_module_flags(void) {
    return "ENCODER";
}

#else

void encoder_init(void) {
}

void encoder_poll(void) {
}

bool encoder_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    (void)cmd;
    (void)payload;
    (void)len;
    return false;
}

const char *encoder_module_flags(void) {
    return "ENCODER_STUBBED";
}

bool encoder_get_snapshot(uint16_t enc_id,
                          int32_t *out_position,
                          int32_t *out_revolutions,
                          int8_t  *out_direction) {
    (void)enc_id; (void)out_position; (void)out_revolutions; (void)out_direction;
    return false;
}

#endif
