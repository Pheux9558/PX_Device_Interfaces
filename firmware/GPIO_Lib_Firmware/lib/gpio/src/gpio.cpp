// Minimal GPIO HAL that maps to Arduino pin functions when ARDUINO is defined
#include "gpio.h"
#include "cmd.h"

#if defined(ARDUINO)
#include <Arduino.h>
#include <stdlib.h>

// forward declare debug helper so functions defined below can call it
static void _call_dbg(const char *msg);

#include "modules.h"

#define MAX_DIGITAL_INPUTS 16
#define MAX_ANALOG_INPUTS 8
#define GPIO_POLL_INTERVAL_MS 10

struct digital_input_t {
	uint16_t pin;
	uint8_t last;
	volatile bool dirty;
	bool used;
	bool use_interrupt;
};

struct analog_input_t {
	uint16_t pin;
	uint16_t last;
	uint16_t threshold;
	bool used;
	bool initialized;
};

static digital_input_t g_digital_inputs[MAX_DIGITAL_INPUTS];
static analog_input_t g_analog_inputs[MAX_ANALOG_INPUTS];
static uint16_t g_analog_default_threshold = 4;
static uint32_t g_last_poll_ms = 0;

#if defined(ARDUINO_ARCH_ESP32)
static void IRAM_ATTR gpio_digital_isr(void *arg) {
	digital_input_t *entry = (digital_input_t *)arg;
	if (entry) {
		entry->dirty = true;
	}
}

static void gpio_attach_interrupt(digital_input_t *entry) {
	if (!entry) return;
	attachInterruptArg((int)entry->pin, gpio_digital_isr, entry, CHANGE);
	entry->use_interrupt = true;
}
#else
static void gpio_attach_interrupt(digital_input_t *entry) {
	(void)entry;
}
#endif

static digital_input_t *find_digital_input(uint16_t pin) {
	for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
		if (g_digital_inputs[i].used && g_digital_inputs[i].pin == pin) return &g_digital_inputs[i];
	}
	return NULL;
}

static digital_input_t *alloc_digital_input(uint16_t pin) {
	for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
		if (!g_digital_inputs[i].used) {
			g_digital_inputs[i].used = true;
			g_digital_inputs[i].pin = pin;
			g_digital_inputs[i].last = 0;
			g_digital_inputs[i].dirty = true;
			g_digital_inputs[i].use_interrupt = false;
			return &g_digital_inputs[i];
		}
	}
	return NULL;
}

static analog_input_t *find_analog_input(uint16_t pin) {
	for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
		if (g_analog_inputs[i].used && g_analog_inputs[i].pin == pin) return &g_analog_inputs[i];
	}
	return NULL;
}

static analog_input_t *alloc_analog_input(uint16_t pin) {
	for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
		if (!g_analog_inputs[i].used) {
			g_analog_inputs[i].used = true;
			g_analog_inputs[i].pin = pin;
			g_analog_inputs[i].last = 0;
			g_analog_inputs[i].threshold = g_analog_default_threshold;
			g_analog_inputs[i].initialized = false;
			return &g_analog_inputs[i];
		}
	}
	return NULL;
}

static void gpio_send_digital_update(uint16_t pin, uint8_t value) {
	uint8_t resp[2];
	resp[0] = (uint8_t)(pin & 0xFF);
	resp[1] = value & 0xFF;
	cmd_send_response(0x0010, resp, 2);
}

static void gpio_send_analog_update(uint16_t pin, uint16_t value) {
	uint8_t resp[2];
	resp[0] = (uint8_t)(pin & 0xFF);
	resp[1] = (uint8_t)(value & 0xFF);
	cmd_send_response(0x0012, resp, 2);
}

static digital_input_t *gpio_register_digital_input(uint16_t pin) {
	digital_input_t *entry = find_digital_input(pin);
	if (!entry) entry = alloc_digital_input(pin);
	if (!entry) return NULL;
	int v = gpio_digital_read(pin);
	entry->last = (uint8_t)(v & 0xFF);
	entry->dirty = false;
	gpio_attach_interrupt(entry);
	gpio_send_digital_update(pin, entry->last);
	return entry;
}

static analog_input_t *gpio_register_analog_input(uint16_t pin) {
	analog_input_t *entry = find_analog_input(pin);
	if (!entry) entry = alloc_analog_input(pin);
	if (!entry) return NULL;
	int v = gpio_analog_read(pin);
	entry->last = (uint16_t)v;
	entry->initialized = true;
	gpio_send_analog_update(pin, entry->last);
	return entry;
}

void gpio_init() {
	// register module flag at init
	modules_add_flag(gpio_module_flags());
	for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
		g_digital_inputs[i].used = false;
		g_digital_inputs[i].dirty = false;
		g_digital_inputs[i].use_interrupt = false;
	}
	for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
		g_analog_inputs[i].used = false;
		g_analog_inputs[i].initialized = false;
		g_analog_inputs[i].threshold = g_analog_default_threshold;
	}
	g_last_poll_ms = 0;
}
void gpio_digital_write(uint16_t pin, uint8_t value) {
	digitalWrite((int)pin, value ? HIGH : LOW);
	char b[64];
	snprintf(b, sizeof(b), "gpio: digital_write pin=%u val=%u", (unsigned)pin, (unsigned)value);
	_call_dbg(b);
}

int gpio_digital_read(uint16_t pin) {
	int v = digitalRead((int)pin) == HIGH ? 1 : 0;
	char b[64];
	snprintf(b, sizeof(b), "gpio: digital_read pin=%u val=%u", (unsigned)pin, (unsigned)v);
	_call_dbg(b);
	return v;
}

void gpio_analog_write(uint16_t pin, uint16_t value) {
	analogWrite((int)pin, (int)value);
	char b[64];
	snprintf(b, sizeof(b), "gpio: analog_write pin=%u val=%u", (unsigned)pin, (unsigned)value);
	_call_dbg(b);
}

int gpio_analog_read(uint16_t pin) {
	int v = analogRead((int)pin);
	char b[64];
	snprintf(b, sizeof(b), "gpio: analog_read pin=%u val=%d", (unsigned)pin, v);
	_call_dbg(b);
	return v;
}

// Debug callback storage and helper
static gpio_debug_cb_t g_debug_cb = NULL;

void gpio_set_debug_cb(gpio_debug_cb_t cb) { g_debug_cb = cb; }

// forward declare debug helper so other functions can call it before it's defined
static void _call_dbg(const char *msg);

static void _call_dbg(const char *msg) {
	if (g_debug_cb) {
		g_debug_cb(msg);
	}
}

// Setup helpers
void gpio_set_mode(uint16_t pin, uint8_t mode) {
	if (mode) {
		pinMode((int)pin, OUTPUT);
		char b[64];
		snprintf(b, sizeof(b), "gpio: set pin %u MODE=OUTPUT", (unsigned)pin);
		_call_dbg(b);
	} else {
		pinMode((int)pin, INPUT);
		char b[64];
		snprintf(b, sizeof(b), "gpio: set pin %u MODE=INPUT", (unsigned)pin);
		_call_dbg(b);
	}
}

void gpio_set_pull(uint16_t pin, uint8_t pull) {
	if (pull == 1) {
		// pull-up
		pinMode((int)pin, INPUT_PULLUP);
		char b[64];
		snprintf(b, sizeof(b), "gpio: set pin %u PULL=UP", (unsigned)pin);
		_call_dbg(b);
	} else if (pull == 2) {
#if defined(INPUT_PULLDOWN)
		pinMode((int)pin, INPUT_PULLDOWN);
#else
		pinMode((int)pin, INPUT);
#endif
		char b[64];
		snprintf(b, sizeof(b), "gpio: set pin %u PULL=DOWN", (unsigned)pin);
		_call_dbg(b);
	} else {
		// no pull
		pinMode((int)pin, INPUT);
		char b[64];
		snprintf(b, sizeof(b), "gpio: set pin %u PULL=NONE", (unsigned)pin);
		_call_dbg(b);
	}
}

void gpio_attach_servo(uint16_t pin, uint8_t index) {
	// Minimal stub: user firmware may include Servo support.
	// For now just ensure the pin is set to output so attach or writes work.
	pinMode((int)pin, OUTPUT);
	char b[64];
	snprintf(b, sizeof(b), "gpio: attach servo idx=%u pin=%u", (unsigned)index, (unsigned)pin);
	_call_dbg(b);
}

// Command handling implementation
#include "cmd.h"

bool gpio_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len) {
	// handle setup commands and digital in/out
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
				gpio_register_digital_input(pin);
			}
			cmd_send_ok();
			return true;
		case 0x0002: // digital input pullup
			if (len >= 1) {
				uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				gpio_set_pull(pin, 1);
				gpio_register_digital_input(pin);
			}
			cmd_send_ok();
			return true;
		case 0x0003: // digital input pulldown
			if (len >= 1) {
				uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				gpio_set_pull(pin, 2);
				gpio_register_digital_input(pin);
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
				gpio_register_analog_input(pin);
			}
			cmd_send_ok();
			return true;
		case 0x000B: // analog tolerance / threshold
			if (len < 1) { cmd_send_error(); return true; }
			if (len == 1) {
				g_analog_default_threshold = payload[0];
				cmd_send_ok();
				return true;
			}
			{
				uint16_t pin = (len >= 3) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				uint8_t threshold = (len >= 3) ? payload[2] : payload[1];
				analog_input_t *entry = find_analog_input(pin);
				if (!entry) { cmd_send_error(); return true; }
				entry->threshold = threshold;
				cmd_send_ok();
				return true;
			}
		case 0x0011: // digital write
			if (len < 2) { cmd_send_error(); return true; }
			{
				uint16_t pin = (len >= 3) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				uint8_t val = payload[len-1];
				gpio_digital_write(pin, val);
				cmd_send_ok();
			}
			return true;
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
		case 0x0012: // analog read
			if (len < 1) { cmd_send_error(); return true; }
			{
				uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				int v = gpio_analog_read(pin);
				gpio_send_analog_update(pin, (uint16_t)v);
			}
			return true;
		case 0x0013: // analog write
			if (len < 2) { cmd_send_error(); return true; }
			{
				uint16_t pin = (len >= 3) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				uint16_t val = payload[len-1];
				gpio_analog_write(pin, val);
				cmd_send_ok();
			}
			return true;
		default:
			return false;
	}
}

void gpio_poll_inputs() {
	uint32_t now = millis();
	if ((uint32_t)(now - g_last_poll_ms) < GPIO_POLL_INTERVAL_MS) return;
	g_last_poll_ms = now;

	for (int i = 0; i < MAX_DIGITAL_INPUTS; ++i) {
		digital_input_t *entry = &g_digital_inputs[i];
		if (!entry->used) continue;
		if (entry->use_interrupt && !entry->dirty) continue;
		int v = gpio_digital_read(entry->pin);
		if ((uint8_t)v != entry->last) {
			entry->last = (uint8_t)v;
			gpio_send_digital_update(entry->pin, entry->last);
		}
		entry->dirty = false;
	}

	for (int i = 0; i < MAX_ANALOG_INPUTS; ++i) {
		analog_input_t *entry = &g_analog_inputs[i];
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

const char *gpio_module_flags() {
	return "GPIO";
}
#endif
