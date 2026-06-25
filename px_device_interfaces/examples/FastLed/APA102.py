import argparse
import signal
import sys
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig

# source /home/pheux/Documents/projects/0_python/PX_Device_Interfaces/.venv/bin/activate 2>/dev/null || true && python -m px_device_interfaces.examples.FastLed.APA102 --data-pin 40 --clock-pin 39 --count 30 --hold 0.5 --port /dev/ttyACM0

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generic APA102 (DotStar) demo for GPIO_Lib"
    )
    parser.add_argument("--port", default=None, help="Optional serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=921600, help="Optional baud rate")
    parser.add_argument("--debug", action="store_true", help="Enable transport debug logs")

    parser.add_argument("--data-pin", type=int, default=40, help="APA102 data pin")
    parser.add_argument("--clock-pin", type=int, default=39, help="APA102 clock pin")
    parser.add_argument("--count", type=int, default=1, help="Number of LEDs")

    parser.add_argument("--hold", type=float, default=0.2, help="Seconds to hold each color")

    parser.add_argument(
        "--send-ack-timeout",
        type=float,
        default=0.5,
        help="GPIO_Lib send ACK timeout in seconds",
    )
    return parser.parse_args()


def build_transport_config(args: argparse.Namespace) -> USBTransportConfig:
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


def run_color_sequence(strip, hold: float) -> None:
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
        (0, 0, 0),
    ]

    for color in colors:
        strip.send_led_data([color] * strip.led_count)
        time.sleep(hold)


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
    gpio_lib = GPIO_Lib(transport_config=config, send_ack_timeout=args.send_ack_timeout)
    install_signal_handlers(gpio_lib)

    gpio_lib.start()

    try:
        strip = gpio_lib.FastLED.FastLEDAPA102(
            gpio_lib=gpio_lib,
            data_pin=args.data_pin,
            clock_pin=args.clock_pin,
            led_count=args.count,
        )
        strip.setup()

        run_color_sequence(strip, hold=args.hold)

        run_brightness_sweep(strip)

        gpio_lib.await_send_empty()
        print("APA102 demo complete.")
    except Exception as e:
        print(f"Error during APA102 demo:\n{e}")
    finally:
        gpio_lib.stop()


if __name__ == "__main__":
    main()
