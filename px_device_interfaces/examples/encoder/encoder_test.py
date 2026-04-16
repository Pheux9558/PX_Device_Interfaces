import argparse
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig

# Example usage:
#   .venv/bin/python -m px_device_interfaces.examples.encoder.encoder_test --pin-a 0 --pin-b 1 --ppr 600

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Encoder smoke test")
    p.add_argument("--port", default=None, help="Optional serial port (auto-connect if omitted)")
    p.add_argument("--baud", type=int, default=921600, help="Serial baud rate")
    p.add_argument("--pin-a", type=int, default=0, help="Encoder A pin")
    p.add_argument("--pin-b", type=int, default=1, help="Encoder B pin")
    p.add_argument("--pin-z", type=int, default=None, help="Optional encoder Z pin")
    p.add_argument("--ppr", type=int, default=1024, help="Encoder pulses per revolution")
    p.add_argument("--duration", type=float, default=20.0, help="Read duration in seconds")
    p.add_argument("--interval", type=float, default=0.1, help="Read interval in seconds")
    p.add_argument("--debug", action="store_true", help="Enable transport debug")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = USBTransportConfig(port=args.port, baud=args.baud, debug=args.debug, auto_connect=True)
    gpio = GPIO_Lib(transport_config=cfg, send_ack_timeout=1.5)
    gpio.start()

    try:
        enc = gpio.Encoder(
            gpio_lib=gpio,
            pin_a=args.pin_a,
            pin_b=args.pin_b,
            pin_z=args.pin_z,
            ppr=args.ppr,
        )
        enc.setup()
        gpio.await_send_empty()

        print("Rotate encoder now. Reading wrapped position/revolutions...")
        deadline = time.time() + args.duration
        while time.time() < deadline:
            state = enc.read(timeout=1.0)
            print(
                f"pos={state['position']:>5d} rev={state.get('revolutions', 0):>6d} dir={state['direction']:>2d} z={int(state['z'])}",
                end="\r",
                flush=True,
            )
            time.sleep(args.interval)
        print()
    finally:
        gpio.await_send_empty()
        gpio.stop()


if __name__ == "__main__":
    main()
