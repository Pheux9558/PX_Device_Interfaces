#!/usr/bin/env python3
"""Blink LED13 using `GPIO_Lib` with configuration files.

This script demonstrates the intended flow:
- write a Connection_Organiser settings JSON for device `led13` (USB port/baud)
- write a `sys_files/GPIO_Lib/led13.data` file mapping pin 13 to name `LED13`
- create `GPIO_Lib('led13')`, call `start()`, then toggle the named output.

It overwrites existing settings/config for simplicity.
"""
from __future__ import annotations

import os
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig


PORT = "/dev/ttyACM0"
BAUD = 115200


def make_connection_settings(device: str, port: str, baud: int) -> dict:
    return {"type": "USB", "port": port, "baud": int(baud)}


def ensure_gpio_config(device: str) -> None:
    d = os.path.join("sys_files", "GPIO_Lib")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{device}.data")
    # simple mapping: make pin 13 an output named LED13
    with open(path, "w") as f:
        f.write(">output 13 LED13\n")


def main() -> None:
    cfg = USBTransportConfig(port=PORT, baud=BAUD, timeout=0.1, debug=True)
    gpio = GPIO_Lib(transport_config=cfg, auto_io=True, debug_enabled=True, require_ack_on_send=False)
    try:
        gpio.start()
        # configure pin mapping at runtime (no filesystem writes)
        gpio.pin_mode(13, "OUTPUT", name="LED13")
        print("Turning LED13 ON")
        gpio.digital_write("LED13", True)
        time.sleep(1.0)
        print("Turning LED13 OFF")
        gpio.digital_write("LED13", False)
    finally:
        time.sleep(0.5)
        gpio.stop()


if __name__ == "__main__":
    main()
