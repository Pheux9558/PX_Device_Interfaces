#!/usr/bin/env python3
"""Quick test: blink LED on pin 10 using USB on COM7.

Usage: run manually on the host connected to the device on COM7.
"""
from __future__ import annotations

import time
from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig

port = "COM7"
baud = 115200
led_pin = 10
blink_count = 100



def main() -> int:
    # Create GPIO_Lib with explicit transport config (USB on COM7)
    conf = USBTransportConfig(port=port, baud=baud, timeout=0, debug=True, auto_io=True)
    gpio = GPIO_Lib(transport_config=conf, require_ack_on_send=True, debug_enabled=True)
    try:
        gpio.start()

        # configure pin 10 as OUTPUT with name LED_BUILTIN
        gpio.pin_mode(led_pin, "OUTPUT", name="LED_BUILTIN")

        print(f"Blinking pin {led_pin} (LED_BUILTIN) on COM7 - {blink_count} times")
        for i in range(blink_count):
            gpio.digital_write("LED_BUILTIN", False) # invert logic: LOW = ON
            time.sleep(0.01)
            gpio.digital_write("LED_BUILTIN", True) # invert logic: HIGH = OFF
            time.sleep(0.01)

        print("Done blinking")

        time.sleep(0.5)
    except Exception as e:
        print(f"Error during GPIO_Lib operation: {e}")
    finally:
        try:
            if gpio._send_q.qsize() != 0:
                print(f"Waiting for send queue to empty before stopping... Remaining items: {gpio._send_q.qsize()}")
                gpio.await_send_empty(5)
                print(f"Send queue size before stopping: {gpio._send_q.qsize()}")
            gpio.stop()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
