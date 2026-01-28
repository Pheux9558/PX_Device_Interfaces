#!/usr/bin/env python3
"""Blink a specified pin using `GPIO_Lib` and a small config file.

Usage examples:
  # blink pin 13
  python3 python/examples/blink_pin_configured.py --pin 13

  # blink pin 5 and invert logic (active-low)
  python3 python/examples/blink_pin_configured.py --pin 5 --invert

This script writes connection settings for a device name and creates the
`sys_files/GPIO_Lib/<device>.data` mapping for the requested pin, then
starts `GPIO_Lib` and blinks the named output.
"""
from __future__ import annotations

import argparse
import os
import time
import sys
from pathlib import Path

# Ensure the repository root is on `sys.path` when running this example
# directly from `python/examples` so `from python.*` imports succeed.
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig


DEFAULT_DEVICE = "led_test"
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200


def make_connection_settings(device: str, port: str, baud: int) -> dict:
    return {"type": "USB", "port": port, "baud": int(baud)}


def main() -> None:
    p = argparse.ArgumentParser(description="Blink a pin using GPIO_Lib and a small config file")
    p.add_argument("--device", default=DEFAULT_DEVICE, help="device name for sys_files and settings")
    p.add_argument("--port", default=DEFAULT_PORT, help="serial port (override)")
    p.add_argument("--baud", default=DEFAULT_BAUD, type=int, help="baud rate")
    p.add_argument("--pin", required=True, type=int, help="pin number to blink")
    p.add_argument("--invert", action="store_true", help="invert logic when writing (active-low)")
    p.add_argument("--count", type=int, default=5, help="number of blinks")
    p.add_argument("--on-ms", type=float, default=0.4, help="milliseconds the LED is ON per blink (seconds)")
    p.add_argument("--off-ms", type=float, default=0.4, help="milliseconds the LED is OFF per blink (seconds)")
    p.add_argument("--debug", action="store_true", help="enable debug prints in GPIO_Lib")
    args = p.parse_args()

    device = args.device
    pin = args.pin
    name = "BLINK"

    # create GPIO_Lib with explicit transport config
    cfg = USBTransportConfig(port=args.port, baud=args.baud, timeout=0.1, debug=bool(args.debug))
    gpio = GPIO_Lib(transport_config=cfg, auto_io=True, debug_enabled=bool(args.debug), require_ack_on_send=False)
    try:
        gpio.start()
        # configure pin mapping at runtime
        gpio.pin_mode(pin, "OUTPUT", name=name)
        print(f"Blinking pin {pin} as '{name}' (invert={args.invert})")
        for i in range(args.count):
            # write True for ON; invert if requested
            on_val = not args.invert
            gpio.digital_write(name, on_val)
            time.sleep(args.on_ms)
            gpio.digital_write(name, not on_val)
            time.sleep(args.off_ms)
    finally:
        time.sleep(0.05)
        gpio.stop()
        print(gpio.debug_ok_received, "OK messages received from device")


if __name__ == "__main__":
    main()
