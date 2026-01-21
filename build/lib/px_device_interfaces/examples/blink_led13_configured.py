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

from px_device_interfaces.settings_manager import load_connection_settings, save_connection_settings
from px_device_interfaces.GPIO_Lib import GPIO_Lib


DEVICE_NAME = "led_test"
PORT = "/dev/ttyACM0"
BAUD = 115200


def ensure_connection_settings(device: str, port: str, baud: int) -> None:
    s = load_connection_settings(device)
    s.set("type", "USB")
    # the settings manager stores arbitrary keys in data
    s.set("port", port)
    s.set("baud", baud)
    save_connection_settings(device, s)


def ensure_gpio_config(device: str) -> None:
    d = os.path.join("sys_files", "GPIO_Lib")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{device}.data")
    # simple mapping: make pin 13 an output named LED13
    with open(path, "w") as f:
        f.write(">output 13 LED13\n")


def main() -> None:
    ensure_connection_settings(DEVICE_NAME, PORT, BAUD)
    ensure_gpio_config(DEVICE_NAME)

    gpio = GPIO_Lib(DEVICE_NAME, auto_io=True, debug=True)
    try:
        gpio.start()

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
