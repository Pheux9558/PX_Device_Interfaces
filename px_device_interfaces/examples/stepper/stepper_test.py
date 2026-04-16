"""STSPIN220 stepper driver smoke test.

Usage::

    # Real hardware
    python -m px_device_interfaces.examples.stepper.stepper_test --port /dev/ttyACM0

    # Offline (no hardware needed)
    python -m px_device_interfaces.examples.stepper.stepper_test --mock

Edit the PIN constants below to match your wiring.
"""
import argparse
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.transports.mock import MockTransportConfig

# ── Pin assignments ───────────────────────────────────────────────────────────
STEP_PIN  = 2
DIR_PIN   = 3
EN_PIN    = 4
M0_PIN    = 5
M1_PIN    = 6
SLP_PIN   = 9
FAULT_PIN = 10


def _poll_until_stopped(stepper, max_polls: int = 50) -> None:
    for _ in range(max_polls):
        status = stepper.get_status()
        print(
            f"  pos={status['position']:8.3f} {status['unit_mode']}  speed={status['speed']:7.3f}  "
            f"moving={int(status['moving'])}  fault={int(status['fault'])}",
            end="\r",
            flush=True,
        )
        if not status["moving"]:
            break
        time.sleep(0.1)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="STSPIN220 stepper smoke test")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--mock", action="store_true",
                        help="Use MockTransport (no hardware needed)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.mock:
        gpio = GPIO_Lib(transport_config=MockTransportConfig())
        print("[MockTransport] offline mode — commands sent to /dev/null.")
    else:
        cfg = USBTransportConfig(port=args.port, baud_rate=args.baud, debug=args.debug)
        gpio = GPIO_Lib(transport_config=cfg)

    try:
        gpio.start()
        if not args.mock:
            time.sleep(0.5)

        stepper = gpio.Stepper.StepperSTSPIN220(
            gpio,
            step_pin=STEP_PIN,
            dir_pin=DIR_PIN,
            enable_pin=EN_PIN,
            m0_pin=M0_PIN,
            m1_pin=M1_PIN,
            sleep_pin=SLP_PIN,
            fault_pin=FAULT_PIN,
            steps_per_revolution=200,
            max_speed=800,
            acceleration=400,
        )
        stepper.setup()
        stepper.set_microstepping_mode(GPIO_Lib.Stepper.MICROSTEPS.X1_32)
        stepper.initialize()             # Full startup sequence (SLP reset+wakeup)
        stepper.configure_motion_mm(
            steps_per_mm=100.0,
            max_speed_mm_s=8.0,
            max_accel_mm_s2=4.0,
        )

        print("Moving to 5 mm …")
        stepper.move_to_position_mm(5.0, speed=4.0, acceleration=4.0)
        _poll_until_stopped(stepper)

        print("Returning to origin …")
        stepper.move_to_position_mm(0.0, speed=4.0, acceleration=4.0)
        _poll_until_stopped(stepper)

        print("Moving to 20 mm …")
        stepper.move_to_position_mm(20.0, speed=6.0, acceleration=6.0)
        _poll_until_stopped(stepper)

        print("Decelerating stop test …")
        stepper.move_to_position_mm(35.0, speed=6.0, acceleration=6.0)
        time.sleep(0.4)
        stepper.stop(immediate=False)
        _poll_until_stopped(stepper)

        status = stepper.get_status()
        print(
            f"Final: pos={status['position']:.3f} {status['unit_mode']}  speed={status['speed']:.3f}  "
            f"fault_flags=0x{status['fault_flags']:02X}"
        )
        stepper.stop(immediate=True)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        gpio.stop()


if __name__ == "__main__":
    main()
