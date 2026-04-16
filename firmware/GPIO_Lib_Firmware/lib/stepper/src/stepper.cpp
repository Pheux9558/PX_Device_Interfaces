/**
 * Stepper motor service — complete rewrite.
 *
 * Features:
 *  - Up to MAX_STEPPER_INSTANCES independent stepper instances
 *  - Driver types: GENERIC, STSPIN220, DRV8825
 *  - Trapezoidal acceleration / deceleration profile
 *  - Timer-driven step generation using micros() within a FreeRTOS task
 *    (1 ms scheduling + sub-ms step distribution via busy-spin)
 *  - Fault pin monitoring (active-low) with auto-halt
 *  - Encoder feedback (closed-loop PID speed correction)
 *  - Length-based moves (steps_per_mm)
 *  - Time-based moves (move for N ms at current speed)
 *  - STSPIN220 microstepping latch via SLP pin toggle
 *  - DRV8825 microstepping via separate M0/M1/M2 pins
 *
 * Command map (0x0320 – 0x032F):
 *  0x0320  STEPPER_CREATE          id[2]
 *  0x0321  STEPPER_SET_PINS        id[2] step[1] dir[1] driver_type[1]
 *                                   enable[1] fault[1] sleep[1]
 *                                   m0[1] m1[1] m2[1]   (0xFF = not present)
 *  0x0322  STEPPER_SET_ENCODER     id[2] enc_id[2] enc_ppr[2]
 *  0x0323  STEPPER_SET_PID         id[2] kp[4f] ki[4f] kd[4f]
 *  0x0324  STEPPER_SET_MICROSTEP   id[2] divisor[1]
 *  0x0325  STEPPER_CONFIGURE_MOTION id[2] unit_mode[1] steps_per_rev[2]
 *                                   steps_per_mm[4f] max_speed[4f] max_accel[4f]
 *  0x0326  STEPPER_MOVE_TO_UNITS   id[2] unit_mode[1] target[4f]
 *                                   speed_override[4f] accel_override[4f]
 *  0x0327  STEPPER_GET_STATUS      id[2]
 *            → id[2] state[1] unit_mode[1] pos_user[4f] speed_user[4f]
 *               moving[1] fault[1] fault_flags[1] pos_steps[4] speed_sps[4f]
 *  0x0328  STEPPER_STOP            id[2] immediate[1]
 *  0x0329  STEPPER_ENABLE          id[2] enable[1]
 *  0x032A  STEPPER_CONFIGURE_HOMING id[2] speed[4f] accel[4f] left_pin[1]
 *                                   right_pin[1] flags[1]
 *  0x032B  STEPPER_HOME            id[2]
 *  0x032C  STEPPER_SET_DIRECTION   id[2] invert[1]
 *  0x032D  STEPPER_SET_POSITION_UNITS id[2] unit_mode[1] position[4f]
 *  0x032E  STEPPER_CLEAR_FAULT     id[2]
 *  0x032F  STEPPER_INIT            id[2] (run driver startup sequence)
 */
#include "stepper.h"

#include "cmd.h"
#include "cmd_auto.h"
#include "modules.h"
#include "../../hal/src/hal_gpio.h"
#include "../../hal/src/hal_time.h"
#include "../../rtosal/src/rtosal.h"
#include "../../encoder/src/encoder.h"

#include <math.h>
#include <string.h>

#if defined(ARDUINO)
#include <Arduino.h>
#endif

#if defined(ARDUINO_ARCH_STM32)
#include <HardwareTimer.h>
#endif

#if defined(STEPPER_SUPPORT)

CMD_REGISTER(0x0320, 0x032F, stepper_cmd_handler)

/* ─────────────────────────────────────────────────────────────────── */
/*  Configuration                                                       */
/* ─────────────────────────────────────────────────────────────────── */

#define MAX_STEPPER_INSTANCES     4
#define STEPPER_TASK_INTERVAL_MS  1       /* step-task scheduling period   */
#define STEPPER_STEP_PULSE_US     2       /* STEP pulse width (µs)         */
#define STEPPER_MIN_SPEED_SPS     5.0f    /* minimum running speed (sps)   */
#define STEPPER_MAX_STEPS_PER_MS  500     /* burst ceiling per 1 ms window */
#define STEPPER_PIN_NONE          0xFF    /* sentinel: pin not present     */

/* ─────────────────────────────────────────────────────────────────── */
/*  Types                                                               */
/* ─────────────────────────────────────────────────────────────────── */

typedef enum {
    STEPPER_DRIVER_GENERIC   = 0,
    STEPPER_DRIVER_STSPIN220 = 1,
    STEPPER_DRIVER_DRV8825   = 2,
} stepper_driver_type_t;

typedef enum {
    STEPPER_UNIT_NONE = 0,
    STEPPER_UNIT_MM   = 1,
    STEPPER_UNIT_REV  = 2,
} stepper_unit_mode_t;

typedef enum {
    STEPPER_STATE_IDLE = 0,
    STEPPER_STATE_ACCELERATING = 1,
    STEPPER_STATE_MOVING = 2,
    STEPPER_STATE_DECELERATING = 3,
    STEPPER_STATE_HOMING = 4,
    STEPPER_STATE_FAULT = 5,
} stepper_motion_state_t;

/* Fault bitmask bits (fault_flags) */
#define STEPPER_FAULT_DRIVER  (1u << 0)   /* driver fault pin asserted */
#define STEPPER_FAULT_STALL   (1u << 1)   /* encoder stall detected    */
#define STEPPER_HOME_FLAG_LEFT_ACTIVE_LOW   (1u << 0)
#define STEPPER_HOME_FLAG_RIGHT_ACTIVE_LOW  (1u << 1)

typedef struct {
    uint16_t  id;
    stepper_driver_type_t driver_type;

    /* Core motion pins */
    uint8_t  pin_step;
    uint8_t  pin_dir;
    uint8_t  pin_enable;   /* 0xFF = not present; active-LOW by default */
    uint8_t  pin_fault;    /* 0xFF = not present; active-LOW input      */
    uint8_t  pin_sleep;    /* STSPIN220 SLP/STBY; 0xFF = not present    */

    /* Microstepping pins (0xFF = not present) */
    uint8_t  pin_m0;
    uint8_t  pin_m1;
    /* Note: for STSPIN220 M2 shares STEP, M3 shares DIR — no extra pin */
    /* For DRV8825 / generic, pin_m2 is an independent pin              */
    uint8_t  pin_m2;

    /* Motion parameters */
    uint16_t steps_per_rev;     /* full-steps / revolution              */
    uint8_t  microstep_div;     /* divisor: 1 2 4 8 16 32 64 128 256   */
    float    max_speed_sps;     /* microsteps/sec at current mode       */
    float    accel_sps2;        /* microsteps/sec²                      */
    float    steps_per_mm;      /* effective microsteps/mm              */
    float    full_steps_per_mm; /* configured full-steps/mm             */
    stepper_unit_mode_t unit_mode;
    float    max_speed_user;
    float    accel_user;

    /* Encoder feedback */
    uint16_t encoder_id;        /* 0xFFFF = not attached                */
    uint16_t encoder_ppr;
    bool     encoder_enabled;

    /* PID (closed-loop speed correction) */
    float kp, ki, kd;
    float pid_integral;
    float pid_last_error;
    uint32_t pid_last_update_ms;

    /* ---- volatile fields written by step task ---- */
    volatile int32_t  current_position;
    volatile int32_t  target_position;
    volatile float    current_speed_sps;
    volatile bool     moving;
    volatile bool     direction_positive;
    volatile float    step_accumulator;   /* DDS fractional-step counter  */
    volatile uint32_t move_end_ms;        /* 0 = no time limit            */
    volatile stepper_motion_state_t motion_state;

    /* Fault */
    volatile bool    fault;
    volatile uint8_t fault_flags;
    uint32_t         last_fault_check_ms;

    bool direction_inverted;
    bool homing_active;
    int8_t homing_seek_direction;
    float homing_speed_user;
    float homing_accel_user;
    uint8_t home_left_pin;
    uint8_t home_right_pin;
    uint8_t home_flags;

    /* State */
    bool used;
    bool active;
    bool initialized;
} stepper_instance_t;

typedef struct {
    stepper_instance_t instances[MAX_STEPPER_INSTANCES];
} stepper_state_t;

/* ─────────────────────────────────────────────────────────────────── */
/*  Module globals                                                      */
/* ─────────────────────────────────────────────────────────────────── */

static stepper_state_t   g_stepper_state;
static rtosal_task_t     g_stepper_task  = NULL;
static rtosal_mutex_t    g_stepper_mutex = NULL;
static uint32_t          g_stepper_last_poll_ms = 0;

#if defined(ARDUINO_ARCH_STM32)
static HardwareTimer    *g_stepper_hw_timer        = nullptr;
static volatile bool     g_stepper_hw_timer_active = false;
#endif

static void stepper_set_enable(stepper_instance_t *st, bool enable);

/* ─────────────────────────────────────────────────────────────────── */
/*  Time helpers                                                        */
/* ─────────────────────────────────────────────────────────────────── */

static uint32_t stepper_now_ms(void) {
    return hal_time_millis();
}

/* micros() is available on Arduino targets via hal_time_micros() */
static inline uint32_t stepper_now_us(void) {
    return hal_time_micros();
}

/* True when enough µs have elapsed since a reference (wrap-safe). */
static inline bool us_elapsed(uint32_t since, uint32_t period) {
    return (uint32_t)(hal_time_micros() - since) >= period;
}

static float stepper_effective_steps_per_rev(const stepper_instance_t *st) {
    if (!st) return 0.0f;
    return (float)st->steps_per_rev * (float)((st->microstep_div == 0) ? 256 : st->microstep_div);
}

static float stepper_effective_steps_per_unit(const stepper_instance_t *st) {
    if (!st) return 0.0f;
    if (st->unit_mode == STEPPER_UNIT_MM) return st->steps_per_mm;
    if (st->unit_mode == STEPPER_UNIT_REV) return stepper_effective_steps_per_rev(st);
    return 0.0f;
}

static float stepper_user_speed_to_sps(const stepper_instance_t *st, float speed_user) {
    if (!st) return 0.0f;
    if (st->unit_mode == STEPPER_UNIT_MM) return speed_user * stepper_effective_steps_per_unit(st);
    if (st->unit_mode == STEPPER_UNIT_REV) return (speed_user / 60.0f) * stepper_effective_steps_per_rev(st);
    return speed_user;
}

static float stepper_user_accel_to_sps2(const stepper_instance_t *st, float accel_user) {
    if (!st) return 0.0f;
    if (st->unit_mode == STEPPER_UNIT_MM) return accel_user * stepper_effective_steps_per_unit(st);
    if (st->unit_mode == STEPPER_UNIT_REV) return (accel_user / 60.0f) * stepper_effective_steps_per_rev(st);
    return accel_user;
}

static int32_t stepper_user_position_to_steps(const stepper_instance_t *st, float position_user) {
    if (!st) return 0;
    if (st->unit_mode == STEPPER_UNIT_MM) {
        return (int32_t)lroundf(position_user * stepper_effective_steps_per_unit(st));
    }
    if (st->unit_mode == STEPPER_UNIT_REV) {
        return (int32_t)lroundf(position_user * stepper_effective_steps_per_rev(st));
    }
    return (int32_t)lroundf(position_user);
}

static float stepper_steps_to_user_position(const stepper_instance_t *st, int32_t position_steps) {
    float denom = stepper_effective_steps_per_unit(st);
    if (denom <= 0.0f) return (float)position_steps;
    return (float)position_steps / denom;
}

static float stepper_sps_to_user_speed(const stepper_instance_t *st, float speed_sps) {
    if (!st) return speed_sps;
    if (st->unit_mode == STEPPER_UNIT_MM) {
        float denom = stepper_effective_steps_per_unit(st);
        return (denom > 0.0f) ? (speed_sps / denom) : 0.0f;
    }
    if (st->unit_mode == STEPPER_UNIT_REV) {
        float denom = stepper_effective_steps_per_rev(st);
        return (denom > 0.0f) ? ((speed_sps / denom) * 60.0f) : 0.0f;
    }
    return speed_sps;
}

static void stepper_recompute_motion_scalars(stepper_instance_t *st) {
    if (!st) return;
    if (st->unit_mode == STEPPER_UNIT_MM) {
        uint8_t div = (st->microstep_div == 0) ? 256 : st->microstep_div;
        st->steps_per_mm = st->full_steps_per_mm * (float)div;
    } else if (st->unit_mode == STEPPER_UNIT_NONE && st->steps_per_mm > 0.0f) {
        st->full_steps_per_mm = st->steps_per_mm / (float)((st->microstep_div == 0) ? 256 : st->microstep_div);
    }

    if (st->max_speed_user > 0.0f) st->max_speed_sps = stepper_user_speed_to_sps(st, st->max_speed_user);
    if (st->accel_user > 0.0f) st->accel_sps2 = stepper_user_accel_to_sps2(st, st->accel_user);
}

static bool stepper_endstop_triggered(uint8_t pin, bool active_low) {
    if (pin == STEPPER_PIN_NONE) return false;
    uint8_t value = 0;
    hal_gpio_read(pin, &value);
    return active_low ? (value == 0) : (value != 0);
}

static void stepper_start_move(stepper_instance_t *st, int32_t target_steps, float speed_sps, float accel_sps2, bool homing_active) {
    if (!st) return;
    if (speed_sps > 0.0f) st->max_speed_sps = speed_sps;
    if (accel_sps2 > 0.0f) st->accel_sps2 = accel_sps2;
    st->target_position    = target_steps;
    st->move_end_ms        = 0;
    st->direction_positive = (target_steps > st->current_position);
    st->current_speed_sps  = STEPPER_MIN_SPEED_SPS;
    st->step_accumulator   = 0.0f;
    st->pid_integral       = 0.0f;
    st->pid_last_error     = 0.0f;
    st->pid_last_update_ms = stepper_now_ms();
    st->moving             = (target_steps != st->current_position);
    st->homing_active      = homing_active;
    st->motion_state       = homing_active ? STEPPER_STATE_HOMING : STEPPER_STATE_ACCELERATING;
    if (st->moving) {
        stepper_set_enable(st, true);
        g_stepper_last_poll_ms = stepper_now_ms();
    }
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Instance management                                                 */
/* ─────────────────────────────────────────────────────────────────── */

static stepper_instance_t *stepper_find(uint16_t id) {
    for (int i = 0; i < MAX_STEPPER_INSTANCES; ++i) {
        if (g_stepper_state.instances[i].used &&
            g_stepper_state.instances[i].id == id) {
            return &g_stepper_state.instances[i];
        }
    }
    return NULL;
}

static stepper_instance_t *stepper_alloc(uint16_t id) {
    for (int i = 0; i < MAX_STEPPER_INSTANCES; ++i) {
        stepper_instance_t *st = &g_stepper_state.instances[i];
        if (!st->used) {
            memset(st, 0, sizeof(stepper_instance_t));
            st->used            = true;
            st->id              = id;
            st->driver_type     = STEPPER_DRIVER_GENERIC;
            st->pin_enable      = STEPPER_PIN_NONE;
            st->pin_fault       = STEPPER_PIN_NONE;
            st->pin_sleep       = STEPPER_PIN_NONE;
            st->pin_m0          = STEPPER_PIN_NONE;
            st->pin_m1          = STEPPER_PIN_NONE;
            st->pin_m2          = STEPPER_PIN_NONE;
            st->steps_per_rev   = 200;
            st->microstep_div   = 1;
            st->max_speed_sps   = 400.0f;
            st->accel_sps2      = 400.0f;
            st->steps_per_mm    = 0.0f;
            st->full_steps_per_mm = 0.0f;
            st->unit_mode       = STEPPER_UNIT_NONE;
            st->max_speed_user  = 0.0f;
            st->accel_user      = 0.0f;
            st->encoder_id      = 0xFFFF;
            st->step_accumulator = 0.0f;
            st->kp              = 0.5f;
            st->ki              = 0.0f;
            st->kd              = 0.1f;
            st->motion_state    = STEPPER_STATE_IDLE;
            st->direction_inverted = false;
            st->homing_active   = false;
            st->homing_seek_direction = -1;
            st->homing_speed_user = 0.0f;
            st->homing_accel_user = 0.0f;
            st->home_left_pin   = STEPPER_PIN_NONE;
            st->home_right_pin  = STEPPER_PIN_NONE;
            st->home_flags      = STEPPER_HOME_FLAG_LEFT_ACTIVE_LOW | STEPPER_HOME_FLAG_RIGHT_ACTIVE_LOW;
            return st;
        }
    }
    return NULL;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Driver enable / disable                                             */
/* ─────────────────────────────────────────────────────────────────── */

static void stepper_set_enable(stepper_instance_t *st, bool enable) {
    if (!st || st->pin_enable == STEPPER_PIN_NONE) return;
    /* Most drivers: EN active-LOW */
    hal_gpio_write(st->pin_enable, enable ? 0 : 1);
    st->moving = enable ? st->moving : false;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Microstepping — driver-specific                                     */
/* ─────────────────────────────────────────────────────────────────── */

/* Return M0/M1/M2/M3 bits for STSPIN220 given divisor.
 * Returns false if divisor is unsupported on this driver.             */
static bool stspin220_divisor_bits(uint8_t div,
                                   uint8_t *m0, uint8_t *m1,
                                   uint8_t *m2, uint8_t *m3) {
    /* Reference: STSPIN220 step-mode truth table.
     * M0 = MODE1, M1 = MODE2, M2 = MODE3(STEP), M3 = MODE4(DIR).
     * For 1/32, 1/128, and 1/256, avoid the alternate encodings that keep
     * MODE1 and MODE2 both LOW after wake, because that forces full-step
     * mode regardless of the latched MODE3/MODE4 state.
     * Divisor 256 is encoded as 0 on the wire (uint8 cannot hold 256). */
    switch (div) {
        case   1: *m0=0; *m1=0; *m2=0; *m3=0; return true;
        case   2: *m0=1; *m1=0; *m2=1; *m3=0; return true;
        case   4: *m0=0; *m1=1; *m2=0; *m3=1; return true;
        case   8: *m0=1; *m1=1; *m2=1; *m3=0; return true;
        case  16: *m0=1; *m1=1; *m2=1; *m3=1; return true;
        case  32: *m0=0; *m1=1; *m2=0; *m3=0; return true;
        case  64: *m0=1; *m1=1; *m2=0; *m3=1; return true;
        case 128: *m0=1; *m1=0; *m2=0; *m3=0; return true;
        case   0: *m0=1; *m1=1; *m2=0; *m3=0; return true; /* 256x */
        default:  return false;
    }
}

static bool drv8825_divisor_bits(uint8_t div,
                                  uint8_t *m0, uint8_t *m1, uint8_t *m2) {
    switch (div) {
        case  1: *m0=0; *m1=0; *m2=0; return true;
        case  2: *m0=1; *m1=0; *m2=0; return true;
        case  4: *m0=0; *m1=1; *m2=0; return true;
        case  8: *m0=1; *m1=1; *m2=0; return true;
        case 16: *m0=0; *m1=0; *m2=1; return true;
        case 32: *m0=1; *m1=0; *m2=1; return true;
        default: return false;
    }
}

/**
 * Apply microstepping mode to the driver hardware.
 * For STSPIN220: uses SLP-low → configure M0/M1/STEP/DIR → SLP-high latch.
 * For DRV8825:   writes M0/M1/M2 directly.
 * For GENERIC:   nothing (microstep_div is honoured only in software).
 */
static void stepper_apply_microstep(stepper_instance_t *st, uint8_t div) {
    if (!st || !st->active) return;

    if (st->driver_type == STEPPER_DRIVER_STSPIN220) {
        uint8_t m0, m1, m2, m3;
        if (!stspin220_divisor_bits(div, &m0, &m1, &m2, &m3)) return;

        bool was_enabled = (st->pin_enable == STEPPER_PIN_NONE) ? true : true;
        if (st->pin_enable != STEPPER_PIN_NONE) {
            stepper_set_enable(st, false);
            hal_time_delay_ms(1);
        }

        /* 1. Assert SLP LOW and keep STEP low while the mode pins settle. */
        if (st->pin_sleep != STEPPER_PIN_NONE)
            hal_gpio_write(st->pin_sleep, 0);
        hal_gpio_write(st->pin_step, 0);
        hal_gpio_write(st->pin_dir, 0);
        hal_time_delay_ms(1);

        /* 2. Drive mode inputs while SLP is low. STEP/DIR are repurposed as M2/M3. */
        if (st->pin_m0 != STEPPER_PIN_NONE) hal_gpio_write(st->pin_m0, m0);
        if (st->pin_m1 != STEPPER_PIN_NONE) hal_gpio_write(st->pin_m1, m1);
        hal_gpio_write(st->pin_step, m2);   /* M2 uses STEP pin */
        hal_gpio_write(st->pin_dir,  m3);   /* M3 uses DIR  pin */

        /* 3. Hold substantially longer than the datasheet minimum to avoid marginal latching. */
        hal_time_delay_us(200);

        /* 4. Release SLP HIGH — mode latches on the LOW→HIGH edge. */
        if (st->pin_sleep != STEPPER_PIN_NONE)
            hal_gpio_write(st->pin_sleep, 1);

        /* 5. Wait longer for analog wake-up and digital mode latch to stabilise. */
        hal_time_delay_ms(5);

        /* 6. Restore live STEP/DIR signalling and optionally re-enable outputs. */
        hal_gpio_write(st->pin_step, 0);
        hal_gpio_write(st->pin_dir, (st->direction_positive ^ st->direction_inverted) ? 1 : 0);
        if (st->pin_enable != STEPPER_PIN_NONE && was_enabled) {
            stepper_set_enable(st, true);
            hal_time_delay_ms(1);
        }

        st->microstep_div = div;

    } else if (st->driver_type == STEPPER_DRIVER_DRV8825) {
        uint8_t m0, m1, m2;
        if (!drv8825_divisor_bits(div, &m0, &m1, &m2)) return;

        if (st->pin_m0 != STEPPER_PIN_NONE) hal_gpio_write(st->pin_m0, m0);
        if (st->pin_m1 != STEPPER_PIN_NONE) hal_gpio_write(st->pin_m1, m1);
        if (st->pin_m2 != STEPPER_PIN_NONE) hal_gpio_write(st->pin_m2, m2);

        hal_time_delay_us(1);
        st->microstep_div = div;

    } else {
        /* Generic: no hardware interaction */
        st->microstep_div = div;
    }

    stepper_recompute_motion_scalars(st);
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Driver initialisation (startup sequence)                            */
/* ─────────────────────────────────────────────────────────────────── */

static void stepper_driver_init(stepper_instance_t *st) {
    if (!st || !st->active) return;

    if (st->driver_type == STEPPER_DRIVER_STSPIN220) {
        /* Assert SLP LOW to reset the driver, then latch the desired
         * microstep mode in a single SLP LOW→HIGH edge.
         * stepper_apply_microstep handles the full sequence:
         *   SLP=0 → set M0/M1/STEP(M2)/DIR(M3) → 10µs → SLP=1 → 2ms wait → STEP/DIR restore.
         * Doing a preliminary full-step latch here is wrong: if the driver
         * does not reliably accept a second SLP pulse immediately, it stays
         * in full-step mode, ignoring the second latch. */
        stepper_apply_microstep(st, st->microstep_div);

    } else if (st->driver_type == STEPPER_DRIVER_DRV8825) {
        /* Apply microstep mode then enable */
        stepper_apply_microstep(st, st->microstep_div);

    } else {
        /* Generic: nothing special */
    }

    /* Ensure STEP is low and DIR reflects default direction */
    hal_gpio_write(st->pin_step, 0);
    hal_gpio_write(st->pin_dir, st->direction_inverted ? 1 : 0);

    /* Enable driver if enable pin present */
    stepper_set_enable(st, true);

    st->initialized = true;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Speed / acceleration profile                                        */
/* ─────────────────────────────────────────────────────────────────── */

/**
 * Update current_speed_sps once per task tick (dt_s = tick interval in s).
 * Uses trapezoidal ramp: accelerate toward max_speed, decelerate near target.
 */
static void stepper_update_speed(stepper_instance_t *st, float dt_s) {
    float accel      = (float)st->accel_sps2;
    float max_speed  = (float)st->max_speed_sps;
    float v          = st->current_speed_sps;

    if (v < STEPPER_MIN_SPEED_SPS) v = STEPPER_MIN_SPEED_SPS;

    float dv = accel * dt_s;    /* speed change this tick            */

    float target_speed;

    if (st->move_end_ms != 0) {
        /* Time-limited move: run at max speed */
        target_speed = max_speed;
    } else {
        int32_t remaining = (int32_t)(st->target_position - st->current_position);
        if (remaining < 0) remaining = -remaining;

        /* Distance needed to decelerate to minimum: v²/(2a) */
        float brake_steps = (accel > 0.0f) ? (v * v) / (2.0f * accel) : 0.0f;

        if ((float)remaining <= brake_steps) {
            /* Deceleration ramp */
            float v_at_target = sqrtf(2.0f * accel * (float)remaining);
            target_speed = (v_at_target < STEPPER_MIN_SPEED_SPS)
                         ? STEPPER_MIN_SPEED_SPS : v_at_target;
        } else {
            target_speed = max_speed;
        }
    }

    if (v < target_speed) {
        v += dv;
        if (v > target_speed) v = target_speed;
        if (!st->homing_active) st->motion_state = STEPPER_STATE_ACCELERATING;
    } else if (v > target_speed) {
        v -= dv;
        if (v < target_speed) v = target_speed;
        if (!st->homing_active) st->motion_state = STEPPER_STATE_DECELERATING;
    } else if (!st->homing_active) {
        st->motion_state = STEPPER_STATE_MOVING;
    }

    if (v < STEPPER_MIN_SPEED_SPS) v = STEPPER_MIN_SPEED_SPS;
    if (v > st->max_speed_sps) v = st->max_speed_sps;

    st->current_speed_sps = v;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Fault detection                                                     */
/* ─────────────────────────────────────────────────────────────────── */

static void stepper_check_fault(stepper_instance_t *st) {
    if (st->pin_fault == STEPPER_PIN_NONE) return;

    uint32_t now = stepper_now_ms();
    if ((uint32_t)(now - st->last_fault_check_ms) < 10) return; /* 10ms polling */
    st->last_fault_check_ms = now;

    uint8_t v = 0;
    hal_gpio_read(st->pin_fault, &v);
    if (v == 0) {   /* active-LOW fault signal */
        if (!st->fault) {
            st->fault       = true;
            st->fault_flags |= STEPPER_FAULT_DRIVER;
            stepper_set_enable(st, false);
            st->moving             = false;
            st->current_speed_sps  = 0.0f;
            st->motion_state       = STEPPER_STATE_FAULT;
        }
    }
}

/* ─────────────────────────────────────────────────────────────────── */
/*  PID correction (encoder feedback)                                   */
/* ─────────────────────────────────────────────────────────────────── */

static void stepper_pid_update(stepper_instance_t *st) {
    if (!st->encoder_enabled || st->encoder_id == 0xFFFF) return;
    if (st->kp == 0.0f && st->ki == 0.0f && st->kd == 0.0f) return;

    uint32_t now = stepper_now_ms();
    if ((uint32_t)(now - st->pid_last_update_ms) < 20) return;  /* 20 ms PID tick */
    float dt_pid = (float)((uint32_t)(now - st->pid_last_update_ms)) / 1000.0f;
    st->pid_last_update_ms = now;

    int32_t enc_pos = 0;
    if (!encoder_get_snapshot(st->encoder_id, &enc_pos, NULL, NULL)) return;

    /* Error: commanded steps vs encoder-measured steps.
     * Convert encoder counts to equivalent steps:
     *   enc_steps = enc_pos * (steps_per_rev * microstep_div) / encoder_ppr */
    if (st->encoder_ppr == 0) return;
    float enc_as_steps = (float)enc_pos
                       * ((float)(st->steps_per_rev * st->microstep_div))
                       / (float)st->encoder_ppr;

    float error        = (float)st->current_position - enc_as_steps;
    st->pid_integral  += error * dt_pid;
    float derivative   = (st->pid_last_error != 0.0f)
                       ? (error - st->pid_last_error) / dt_pid
                       : 0.0f;
    st->pid_last_error = error;

    float correction = st->kp * error + st->ki * st->pid_integral
                     + st->kd * derivative;

    /* Apply correction as a speed nudge (± 20% of max speed) */
    float max_corr = (float)st->max_speed_sps * 0.20f;
    if (correction >  max_corr) correction =  max_corr;
    if (correction < -max_corr) correction = -max_corr;

    float new_speed = st->current_speed_sps + correction;
    if (new_speed < STEPPER_MIN_SPEED_SPS)  new_speed = STEPPER_MIN_SPEED_SPS;
    if (new_speed > st->max_speed_sps) new_speed = st->max_speed_sps;

    st->current_speed_sps = new_speed;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Core step execution (called from step task)                         */
/* ─────────────────────────────────────────────────────────────────── */

/** Issue one step pulse and update position.  Returns true if the motor
 *  should continue moving (i.e. move is not yet complete / stopped).  */
static bool stepper_do_step(stepper_instance_t *st) {
    /* ── Check stop conditions ─────────────────────────────────── */
    if (!st->moving || st->fault) {
        st->current_speed_sps = 0.0f;
        st->step_accumulator  = 0.0f;
        stepper_set_enable(st, false);
        st->moving = false;
        st->homing_active = false;
        st->motion_state = st->fault ? STEPPER_STATE_FAULT : STEPPER_STATE_IDLE;
        return false;
    }

    /* Time-limited move? */
    if (st->move_end_ms != 0 &&
        stepper_now_ms() >= st->move_end_ms) {
        st->moving             = false;
        st->current_speed_sps  = 0.0f;
        st->step_accumulator   = 0.0f;
        stepper_set_enable(st, false);
        st->homing_active      = false;
        st->motion_state       = STEPPER_STATE_IDLE;
        return false;
    }

    if (st->homing_active) {
        bool left_triggered = stepper_endstop_triggered(st->home_left_pin, (st->home_flags & STEPPER_HOME_FLAG_LEFT_ACTIVE_LOW) != 0);
        bool right_triggered = stepper_endstop_triggered(st->home_right_pin, (st->home_flags & STEPPER_HOME_FLAG_RIGHT_ACTIVE_LOW) != 0);
        if ((st->homing_seek_direction < 0 && left_triggered) || (st->homing_seek_direction > 0 && right_triggered)) {
            st->current_position = 0;
            st->target_position = 0;
            st->moving = false;
            st->current_speed_sps = 0.0f;
            st->step_accumulator = 0.0f;
            st->homing_active = false;
            st->motion_state = STEPPER_STATE_IDLE;
            stepper_set_enable(st, false);
            return false;
        }
    }

    /* Position-limited move? */
    if (st->move_end_ms == 0) {
        int32_t remaining = st->target_position - st->current_position;
        if (remaining == 0) {
            st->moving             = false;
            st->current_speed_sps  = 0.0f;
            st->step_accumulator   = 0.0f;
            stepper_set_enable(st, false);
            st->homing_active      = false;
            st->motion_state       = STEPPER_STATE_IDLE;
            return false;
        }
        st->direction_positive = (remaining > 0);
    }

    /* ── Set direction ─────────────────────────────────────────── */
    hal_gpio_write(st->pin_dir, (st->direction_positive ^ st->direction_inverted) ? 1 : 0);

    /* ── Issue STEP pulse ──────────────────────────────────────── */
    hal_gpio_write(st->pin_step, 1);
    hal_time_delay_us(STEPPER_STEP_PULSE_US);
    hal_gpio_write(st->pin_step, 0);

    /* ── Update position ────────────────────────────────────────── */
    if (st->direction_positive) st->current_position++;
    else                         st->current_position--;

    return st->moving;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Step task                                                           */
/* ─────────────────────────────────────────────────────────────────── */

static void stepper_task_fn(void *arg) {
    (void)arg;
    modules_add_flag("STEPPER");

    /* DDS tick interval in seconds (matches STEPPER_TASK_INTERVAL_MS) */
    const float dt_s = (float)STEPPER_TASK_INTERVAL_MS * 0.001f;

    rtosal_tick_t wake_time = rtosal_now_ticks();

    while (1) {
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);

        for (int i = 0; i < MAX_STEPPER_INSTANCES; i++) {
            stepper_instance_t *st = &g_stepper_state.instances[i];
            if (!st->used || !st->active || !st->moving || st->fault) continue;

            stepper_check_fault(st);
            if (st->fault) continue;

            stepper_pid_update(st);

            /* Update speed ramp once per tick */
            stepper_update_speed(st, dt_s);

            /* DDS: accumulate fractional steps earned this tick.
             * step_accumulator holds sub-step remainder between ticks. */
            st->step_accumulator += st->current_speed_sps * dt_s;

            int steps_due = (int)st->step_accumulator;
            if (steps_due > STEPPER_MAX_STEPS_PER_MS)
                steps_due = STEPPER_MAX_STEPS_PER_MS;
            st->step_accumulator -= (float)steps_due;

            for (int s = 0; s < steps_due; s++) {
                if (!stepper_do_step(st)) break;
            }
        }

        rtosal_mutex_unlock(g_stepper_mutex);
        rtosal_delay_until(&wake_time, STEPPER_TASK_INTERVAL_MS);
    }
}

#if defined(ARDUINO_ARCH_STM32)
static void stepper_hw_timer_callback(void) {
    const float dt_s = 0.001f;
    for (int i = 0; i < MAX_STEPPER_INSTANCES; i++) {
        stepper_instance_t *st = &g_stepper_state.instances[i];
        if (!st->used || !st->active || !st->moving || st->fault) continue;
        stepper_update_speed(st, dt_s);
        st->step_accumulator += st->current_speed_sps * dt_s;
        int steps_due = (int)st->step_accumulator;
        if (steps_due > STEPPER_MAX_STEPS_PER_MS) steps_due = STEPPER_MAX_STEPS_PER_MS;
        st->step_accumulator -= (float)steps_due;
        for (int s = 0; s < steps_due; s++) {
            if (!stepper_do_step(st)) break;
        }
    }
}
#endif

/* Cooperative poll fallback for platforms without RTOS */
void stepper_poll(void) {
#if defined(ARDUINO_ARCH_STM32)
    if (g_stepper_hw_timer_active) return;
#endif
    uint32_t now_ms = stepper_now_ms();
    uint32_t elapsed_ms = (uint32_t)(now_ms - g_stepper_last_poll_ms);
    if (elapsed_ms == 0) return;
    g_stepper_last_poll_ms = now_ms;

    /* Cap the DDS time-step to avoid a burst of steps on the first call
     * after a long idle (e.g. g_stepper_last_poll_ms set at init time). */
    if (elapsed_ms > 20) elapsed_ms = 20;

    if (rtosal_mutex_lock(g_stepper_mutex, 0) != RTOSAL_OK) return;

    /* Scale DDS by actual elapsed time for accurate cooperative polling */
    float dt_s = (float)elapsed_ms * 0.001f;

    for (int i = 0; i < MAX_STEPPER_INSTANCES; i++) {
        stepper_instance_t *st = &g_stepper_state.instances[i];
        if (!st->used || !st->active || !st->moving || st->fault) continue;

        stepper_check_fault(st);
        if (st->fault) continue;

        stepper_pid_update(st);
        stepper_update_speed(st, dt_s);

        st->step_accumulator += st->current_speed_sps * dt_s;

        int steps_due = (int)st->step_accumulator;
        if (steps_due > STEPPER_MAX_STEPS_PER_MS * (int)elapsed_ms)
            steps_due = STEPPER_MAX_STEPS_PER_MS * (int)elapsed_ms;
        st->step_accumulator -= (float)steps_due;

        for (int s = 0; s < steps_due; s++) {
            if (!stepper_do_step(st)) break;
        }
    }

    rtosal_mutex_unlock(g_stepper_mutex);
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Command handler helpers                                             */
/* ─────────────────────────────────────────────────────────────────── */

static inline uint16_t pu16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}
static inline uint32_t pu32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline int32_t pi32(const uint8_t *p) {
    return (int32_t)pu32(p);
}
static inline float pf32(const uint8_t *p) {
    float f; memcpy(&f, p, 4); return f;
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Command handler                                                     */
/* ─────────────────────────────────────────────────────────────────── */

bool stepper_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    switch (cmd) {

    /* ── 0x0320  CREATE ─────────────────────────────────────────── */
    case 0x0320: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) st = stepper_alloc(id);
        rtosal_mutex_unlock(g_stepper_mutex);
        if (!st) { cmd_send_error(); return true; }
        cmd_send_ok();
        return true;
    }

    /* ── 0x0321  SET_PINS ───────────────────────────────────────── */
    case 0x0321: {
        /* payload: id[2] step[1] dir[1] driver_type[1]
         *          enable[1] fault[1] sleep[1]
         *          m0[1] m1[1] m2[1]   (0xFF = not present)          */
        if (len < 4) { cmd_send_error(); return true; }
        uint16_t id          = pu16(payload);
        uint8_t  pin_step    = payload[2];
        uint8_t  pin_dir     = payload[3];
        uint8_t  driver_type = (len > 4) ? payload[4] : STEPPER_DRIVER_GENERIC;
        uint8_t  pin_enable  = (len > 5) ? payload[5] : STEPPER_PIN_NONE;
        uint8_t  pin_fault   = (len > 6) ? payload[6] : STEPPER_PIN_NONE;
        uint8_t  pin_sleep   = (len > 7) ? payload[7] : STEPPER_PIN_NONE;
        uint8_t  pin_m0      = (len > 8) ? payload[8] : STEPPER_PIN_NONE;
        uint8_t  pin_m1      = (len > 9) ? payload[9] : STEPPER_PIN_NONE;
        uint8_t  pin_m2      = (len >10) ? payload[10]: STEPPER_PIN_NONE;

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }

        st->pin_step    = pin_step;
        st->pin_dir     = pin_dir;
        st->pin_enable  = pin_enable;
        st->pin_fault   = pin_fault;
        st->pin_sleep   = pin_sleep;
        st->pin_m0      = pin_m0;
        st->pin_m1      = pin_m1;
        st->pin_m2      = pin_m2;
        st->driver_type = (stepper_driver_type_t)driver_type;

        /* Configure pins */
        hal_gpio_mode(pin_step, HAL_GPIO_MODE_OUTPUT);
        hal_gpio_mode(pin_dir,  HAL_GPIO_MODE_OUTPUT);
        hal_gpio_write(pin_step, 0);
        hal_gpio_write(pin_dir,  0);

        if (pin_enable != STEPPER_PIN_NONE) {
            hal_gpio_mode(pin_enable, HAL_GPIO_MODE_OUTPUT);
            hal_gpio_write(pin_enable, 1); /* disabled (active-LOW) */
        }
        if (pin_fault != STEPPER_PIN_NONE)
            hal_gpio_mode(pin_fault, HAL_GPIO_MODE_INPUT_PULLUP);
        if (pin_sleep != STEPPER_PIN_NONE) {
            hal_gpio_mode(pin_sleep, HAL_GPIO_MODE_OUTPUT);
            hal_gpio_write(pin_sleep, 0); /* hold in sleep/reset */
        }
        if (pin_m0 != STEPPER_PIN_NONE) hal_gpio_mode(pin_m0, HAL_GPIO_MODE_OUTPUT);
        if (pin_m1 != STEPPER_PIN_NONE) hal_gpio_mode(pin_m1, HAL_GPIO_MODE_OUTPUT);
        if (pin_m2 != STEPPER_PIN_NONE) hal_gpio_mode(pin_m2, HAL_GPIO_MODE_OUTPUT);

        st->active = true;
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0322  SET_ENCODER ────────────────────────────────────── */
    case 0x0322: {
        if (len < 6) { cmd_send_error(); return true; }
        uint16_t id      = pu16(payload);
        uint16_t enc_id  = pu16(payload + 2);
        uint16_t enc_ppr = pu16(payload + 4);

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->encoder_id      = enc_id;
        st->encoder_ppr     = enc_ppr;
        st->encoder_enabled = (enc_id != 0xFFFF);
        st->pid_integral    = 0.0f;
        st->pid_last_error  = 0.0f;
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0323  SET_PID ────────────────────────────────────────── */
    case 0x0323: {
        if (len < 14) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        float kp = pf32(payload + 2);
        float ki = pf32(payload + 6);
        float kd = pf32(payload + 10);

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->kp = kp; st->ki = ki; st->kd = kd;
        st->pid_integral    = 0.0f;
        st->pid_last_error  = 0.0f;
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0324  SET_MICROSTEP ──────────────────────────────────── */
    case 0x0324: {
        if (len < 3) { cmd_send_error(); return true; }
        uint16_t id  = pu16(payload);
        uint8_t  div = payload[2];
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        stepper_apply_microstep(st, div);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0325  CONFIGURE_MOTION ───────────────────────────────── */
    case 0x0325: {
        if (len < 17) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        uint8_t unit_mode = payload[2];
        uint16_t steps_rev = pu16(payload + 3);
        float steps_per_mm = pf32(payload + 5);
        float max_speed_user = pf32(payload + 9);
        float accel_user = pf32(payload + 13);

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->unit_mode = (stepper_unit_mode_t)unit_mode;
        if (steps_rev > 0) st->steps_per_rev = steps_rev;
        st->full_steps_per_mm = (st->unit_mode == STEPPER_UNIT_MM) ? steps_per_mm : 0.0f;
        st->max_speed_user = max_speed_user;
        st->accel_user = accel_user;
        stepper_recompute_motion_scalars(st);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0326  MOVE_TO_UNITS ──────────────────────────────────── */
    case 0x0326: {
        if (len < 15) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        uint8_t unit_mode = payload[2];
        float target_user = pf32(payload + 3);
        float speed_override = pf32(payload + 7);
        float accel_override = pf32(payload + 11);

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active || st->unit_mode != (stepper_unit_mode_t)unit_mode) {
            rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true;
        }
        int32_t target_steps = stepper_user_position_to_steps(st, target_user);
        float speed_sps = (speed_override > 0.0f) ? stepper_user_speed_to_sps(st, speed_override) : st->max_speed_sps;
        float accel_sps2 = (accel_override > 0.0f) ? stepper_user_accel_to_sps2(st, accel_override) : st->accel_sps2;
        stepper_start_move(st, target_steps, speed_sps, accel_sps2, false);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0327  GET_STATUS ─────────────────────────────────────── */
    case 0x0327: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        uint8_t state = (uint8_t)st->motion_state;
        uint8_t unit_mode = (uint8_t)st->unit_mode;
        float pos_user = stepper_steps_to_user_position(st, st->current_position);
        float speed_user = stepper_sps_to_user_speed(st, st->current_speed_sps);
        uint8_t moving = st->moving ? 1 : 0;
        uint8_t fault = st->fault ? 1 : 0;
        uint8_t fault_flags = st->fault_flags;
        int32_t pos_steps = st->current_position;
        float speed_sps = st->current_speed_sps;
        rtosal_mutex_unlock(g_stepper_mutex);

        uint8_t resp[23];
        resp[0] = (uint8_t)(id & 0xFF);
        resp[1] = (uint8_t)((id >> 8) & 0xFF);
        resp[2] = state;
        resp[3] = unit_mode;
        memcpy(&resp[4], &pos_user, 4);
        memcpy(&resp[8], &speed_user, 4);
        resp[12] = moving;
        resp[13] = fault;
        resp[14] = fault_flags;
        memcpy(&resp[15], &pos_steps, 4);
        memcpy(&resp[19], &speed_sps, 4);
        cmd_send_response(0x0327, resp, 23);
        return true;
    }

    /* ── 0x0328  STOP ───────────────────────────────────────────── */
    case 0x0328: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id        = pu16(payload);
        bool     immediate = (len > 2) ? (payload[2] != 0) : false;

        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }

        if (immediate) {
            st->moving            = false;
            st->current_speed_sps = 0.0f;
            st->move_end_ms       = 0;
            st->homing_active     = false;
            st->motion_state      = STEPPER_STATE_IDLE;
            stepper_set_enable(st, false);
        } else {
            /* Decelerate to stop: set target to current position */
            st->target_position = st->current_position;
            st->move_end_ms     = 0;
            st->motion_state    = STEPPER_STATE_DECELERATING;
        }
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x0329  ENABLE ─────────────────────────────────────────── */
    case 0x0329: {
        if (len < 3) { cmd_send_error(); return true; }
        uint16_t id     = pu16(payload);
        bool     enable = (payload[2] != 0);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        stepper_set_enable(st, enable);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032A  CONFIGURE_HOMING ───────────────────────────────── */
    case 0x032A: {
        if (len < 13) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        float speed_user = pf32(payload + 2);
        float accel_user = pf32(payload + 6);
        uint8_t left_pin = payload[10];
        uint8_t right_pin = payload[11];
        uint8_t flags = payload[12];
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active || st->unit_mode == STEPPER_UNIT_NONE) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->homing_speed_user = speed_user;
        st->homing_accel_user = accel_user;
        st->home_left_pin = left_pin;
        st->home_right_pin = right_pin;
        st->home_flags = flags;
        if (left_pin != STEPPER_PIN_NONE) hal_gpio_mode(left_pin, HAL_GPIO_MODE_INPUT_PULLUP);
        if (right_pin != STEPPER_PIN_NONE) hal_gpio_mode(right_pin, HAL_GPIO_MODE_INPUT_PULLUP);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032B  HOME ────────────────────────────────────────────── */
    case 0x032B: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active || st->unit_mode == STEPPER_UNIT_NONE) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        if (st->homing_speed_user <= 0.0f || st->homing_accel_user <= 0.0f) {
            rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true;
        }

        float speed_sps = stepper_user_speed_to_sps(st, st->homing_speed_user);
        float accel_sps2 = stepper_user_accel_to_sps2(st, st->homing_accel_user);
        if (st->home_left_pin != STEPPER_PIN_NONE) {
            st->homing_seek_direction = -1;
            stepper_start_move(st, st->current_position - 2000000000, speed_sps, accel_sps2, true);
        } else if (st->home_right_pin != STEPPER_PIN_NONE) {
            st->homing_seek_direction = 1;
            stepper_start_move(st, st->current_position + 2000000000, speed_sps, accel_sps2, true);
        } else {
            st->homing_seek_direction = (st->current_position >= 0) ? -1 : 1;
            stepper_start_move(st, 0, speed_sps, accel_sps2, true);
        }
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032C  SET_DIRECTION ───────────────────────────────────── */
    case 0x032C: {
        if (len < 3) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        bool invert = payload[2] != 0;
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->direction_inverted = invert;
        hal_gpio_write(st->pin_dir, ((st->direction_positive ^ st->direction_inverted) ? 1 : 0));
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032D  SET_POSITION_UNITS ──────────────────────────────── */
    case 0x032D: {
        if (len < 7) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        uint8_t unit_mode = payload[2];
        float position_user = pf32(payload + 3);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || st->unit_mode != (stepper_unit_mode_t)unit_mode) {
            rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true;
        }
        int32_t pos_steps = stepper_user_position_to_steps(st, position_user);
        st->current_position = pos_steps;
        st->target_position = pos_steps;
        st->current_speed_sps = 0.0f;
        st->moving = false;
        st->homing_active = false;
        st->motion_state = STEPPER_STATE_IDLE;
        st->move_end_ms = 0;
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032E  CLEAR_FAULT ────────────────────────────────────── */
    case 0x032E: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        st->fault       = false;
        st->fault_flags = 0;
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    /* ── 0x032F  INIT ───────────────────────────────────────────── */
    case 0x032F: {
        if (len < 2) { cmd_send_error(); return true; }
        uint16_t id = pu16(payload);
        rtosal_mutex_lock(g_stepper_mutex, RTOSAL_MAX_DELAY);
        stepper_instance_t *st = stepper_find(id);
        if (!st || !st->active) { rtosal_mutex_unlock(g_stepper_mutex); cmd_send_error(); return true; }
        stepper_driver_init(st);
        rtosal_mutex_unlock(g_stepper_mutex);
        cmd_send_ok();
        return true;
    }

    default:
        return false;
    }
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Module lifecycle                                                     */
/* ─────────────────────────────────────────────────────────────────── */

void stepper_init(void) {
    memset(&g_stepper_state, 0, sizeof(g_stepper_state));
    g_stepper_last_poll_ms = stepper_now_ms();
    rtosal_mutex_create(&g_stepper_mutex);

    rtosal_task_config_t cfg = {
        .name        = "StepperTask",
        .fn          = stepper_task_fn,
        .arg         = &g_stepper_state,
        .stack_words = 4096,
        .priority    = 5,   /* high priority — just below interrupt handlers */
    };
    rtosal_task_create(&cfg, &g_stepper_task);

#if defined(ARDUINO_ARCH_STM32)
    /* TIM4 is chosen deliberately: TIM3_CH4 = PB1 = the SLP pin used by
     * the STSPIN220, so using TIM3 would reconfigure that GPIO in its HAL
     * MspInit callback and break the microstepping-mode latch sequence. */
    g_stepper_hw_timer = new HardwareTimer(TIM4);
    g_stepper_hw_timer->setOverflow(1000, HERTZ_FORMAT);
    g_stepper_hw_timer->attachInterrupt(stepper_hw_timer_callback);
    g_stepper_hw_timer->resume();
    g_stepper_hw_timer_active = true;
#endif
}

const char *stepper_module_flags(void) {
    return "STEPPER";
}

/* ─────────────────────────────────────────────────────────────────── */
/*  Stubbed build (STEPPER_SUPPORT not defined)                         */
/* ─────────────────────────────────────────────────────────────────── */
#else

void stepper_init(void)  {}
void stepper_poll(void)  {}

bool stepper_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
    (void)cmd; (void)payload; (void)len;
    return false;
}

const char *stepper_module_flags(void) { return "STEPPER_STUBBED"; }

#endif /* STEPPER_SUPPORT */
