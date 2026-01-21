// Minimal GPIO HAL that maps to Arduino pin functions when ARDUINO is defined
#include "gpio.h"

#if defined(ARDUINO)
#include <Arduino.h>

// forward declare debug helper so functions defined below can call it
static void _call_dbg(const char *msg);

#include "modules.h"

void gpio_init() {
	// register module flag at init
	modules_add_flag(gpio_module_flags());
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
			}
			cmd_send_ok();
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
		case 0x0010: // digital read
			if (len < 1) { cmd_send_error(); return true; }
			{
				uint16_t pin = (len >= 2) ? (uint16_t)payload[0] | ((uint16_t)payload[1] << 8) : payload[0];
				int v = gpio_digital_read(pin);
				uint8_t resp[2];
				resp[0] = (uint8_t)(pin & 0xFF);
				resp[1] = (uint8_t)(v & 0xFF);
				cmd_send_response(0x1010, resp, 2);
			}
			return true;
		default:
			return false;
	}
}

const char *gpio_module_flags() {
	return "GPIO_MODULE=1.0";
}
#endif
