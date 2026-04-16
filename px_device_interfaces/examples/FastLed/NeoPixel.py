import argparse
import signal
import sys
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generic WS2812/NeoPixel smoke demo for GPIO_Lib"
    )
    parser.add_argument("--port", default=None, help="Optional serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=921600, help="Optional baud rate")
    parser.add_argument("--pin", type=int, default=10, help="NeoPixel data pin")
    parser.add_argument("--count", type=int, default=7, help="Number of LEDs in strip")
    parser.add_argument("--debug", action="store_true", help="Enable transport debug logs")
    parser.add_argument(
        "--hold",
        type=float,
        default=0.35,
        help="Seconds to hold each color frame",
    )
    return parser.parse_args()


def build_transport_config(args: argparse.Namespace) -> USBTransportConfig:
    # Keep auto-connect enabled by default while still allowing explicit port/baud.
    return USBTransportConfig(
        port=args.port,
        baud=args.baud,
        debug=args.debug,
        auto_connect=True,
    )


def install_signal_handlers(gpio_lib: GPIO_Lib) -> None:
    def _cleanup(signum, frame):
        _ = signum, frame
        print("\nInterrupted. Stopping GPIO_Lib...")
        gpio_lib.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)


def run_brightness_sweep(strip) -> None:
    strip.send_led_data([(255, 255, 255)] * strip.led_count)

    for brightness in range(255, 0, -1):
        strip.set_brightness(brightness)
        time.sleep(0.005)

    for brightness in range(0, 255):
        strip.set_brightness(brightness)
        time.sleep(0.005)

    strip.send_led_data([(0, 0, 0)] * strip.led_count)


def main() -> None:
    args = parse_args()

    config = build_transport_config(args)
    gpio_lib = GPIO_Lib(transport_config=config, send_ack_timeout=1.5)
    install_signal_handlers(gpio_lib)

    gpio_lib.start()

    try:
        strip = gpio_lib.FastLED.FastLEDWS2812(
            gpio_lib=gpio_lib,
            data_pin=args.pin,
            led_count=args.count,
        )
        strip.setup()

        frames = [
            [(255, 0, 0)] * strip.led_count,
            [(0, 255, 0)] * strip.led_count,
            [(0, 0, 255)] * strip.led_count,
            [(255, 255, 255)] * strip.led_count,
            [(0, 0, 0)] * strip.led_count,
        ]

        for frame in frames:
            strip.send_led_data(frame)
            time.sleep(args.hold)

        run_brightness_sweep(strip)

        gpio_lib.await_send_empty()
        print("NeoPixel smoke test complete.")
    except Exception as e:
        print(f"Error during NeoPixel test:\n{e}")
    finally:
        gpio_lib.stop()


if __name__ == "__main__":
    main()
