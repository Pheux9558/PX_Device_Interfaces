"""
Small GPIO smoke test for T-Dongle-S3.

Test flow:
1. Configure LED pin 38 as output and blink it 3 times.
2. Configure button pin 0 as INPUT_PULLUP.
3. Read button state every 0.5s for 5 seconds and print the result.

Button note:
- GPIO0 BOOT button is active low.
- Pressed => 0, Released => 1.
"""

import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode
from px_device_interfaces.transports.usb import USBTransportConfig


def main() -> None:
    led_pin = 38
    button_pin = 0

    cfg = USBTransportConfig(debug=False, reset_on_start=True, auto_connect=True)
    gpio = GPIO_Lib(transport_config=cfg, send_ack_timeout=1)

    try:
        started = gpio.start()
        if not (started or gpio.connected):
            raise RuntimeError(
                f"Failed to start/connect: start()={started}, connected={gpio.connected}"
            )
        print(f"Connected to device successfully. start()={started}, connected={gpio.connected}")

        gpio.pinMode(led_pin, PinMode.OUTPUT, "LED")
        gpio.pinMode(button_pin, PinMode.INPUT, "BTN")

        print(f"Blinking LED on pin {led_pin} 3 times...")
        for i in range(3):
            gpio.digital_write("LED", True)
            time.sleep(0.25)
            gpio.digital_write("LED", False)
            time.sleep(0.25)
            print(f"  Blink {i + 1}/3")

        print(f"\nReading button pin {button_pin} for 5 seconds (every 0.5s)...")
        start = time.time()
        sample_index = 1
        while time.time() - start < 5.0:
            val = gpio.digital_read("BTN")
            state = "PRESSED" if val == False else "RELEASED"
            elapsed = time.time() - start
            print(f"[{sample_index:02d}] t={elapsed:0.1f}s raw={val} -> {state}")
            sample_index += 1
            time.sleep(0.5)

        gpio.digital_write("LED", True)
        gpio.await_send_empty()
        print("\nGPIO smoke test complete.")

    finally:
        gpio.stop()


if __name__ == "__main__":
    main()
