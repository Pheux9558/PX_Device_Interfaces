#!/usr/bin/env python3
"""Blink LED 13 for one second using GPIO_Lib over USB.

Usage: python3 python/examples/blink_led13.py

This script uses the `USBTransport` directly and attaches it to a
`GPIO_Lib` instance so we can use `digital_write()` to toggle the pin.
"""
from __future__ import annotations

import threading
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransport


def main() -> None:
    port = "/dev/ttyACM0"
    baud = 115200

    # Create the library (device name is arbitrary when we attach a transport manually)
    gpio = GPIO_Lib("usb_manual", auto_io=True, debug=True)

    # Create and open the USB transport
    usb = USBTransport({"port": port, "baud": baud})
    ok = usb.connect()
    if not ok:
        print(f"Failed to open serial port {port} (check permissions and that device is connected)")
        return

    # Attach the transport and start the receive worker
    gpio._transport = usb
    gpio._running = True
    gpio._recv_thread = threading.Thread(target=gpio._recv_worker, daemon=True)
    gpio._recv_thread.start()

    time.sleep(2)  # wait for device to settle
    try:
        # This board has the LED on inverted logic (active-low).
        # `True` means drive high; to turn the LED ON we must drive low -> send False.
        print("Turning LED13 ON (inverted logic)")
        gpio.digital_write(13, False)
        time.sleep(1.0)
        print("Turning LED13 OFF (inverted logic)")
        gpio.digital_write(13, True)
    finally:
        gpio.stop()
        print("Done")


if __name__ == "__main__":
    main()
