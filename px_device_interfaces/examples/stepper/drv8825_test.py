"""DRV8825 stepper driver smoke test.

Usage::

    # Real hardware
    python -m px_device_interfaces.examples.stepper.drv8825_test --port /dev/ttyACM0

    # Offline (no hardware needed)
    python -m px_device_interfaces.examples.stepper.drv8825_test --mock

Edit the PIN constants below to match your wiring.
"""
import argparse
import time

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.transports.mock import MockTransportConfig

# ── Pin assignments ───────────────────────────────────────────────────────────
STEP_PIN  = 11
DIR_PIN   = 12
EN_PIN    = 13
M0_PIN    = 14
M1_PIN    = 15
M2_PIN    = 16
FAULT_PIN = 17


def _poll_until_stopped(stepper, max_polls: int = 50) -> None:
    for _ in range(max_polls):
        status = stepper.get_status()
        print(
            f"  pos={status['position']:+8d}  speed={status['speed']:7.1f} sps  "
            f"moving={int(status['moving'])}  fault={int(status['fault'])}",
            end="\r",
            flush=True,
        )
        if not status["moving"]:
            break
        time.sleep(0.1)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="DRV8825 stepper smoke test")
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
        cfg = USBTransportConfig(port=args.port, baud=args.baud, debug=args.debug)
        gpio = GPIO_Lib(transport_config=cfg)

    try:
        gpio.start()
        if not args.mock:
            time.sleep(0.5)

        stepper = gpio.Stepper.StepperDRV8825(
            gpio,
            step_pin=STEP_PIN,
            dir_pin=DIR_PIN,
            enable_pin=EN_PIN,
            m0_pin=M0_PIN,
            m1_pin=M1_PIN,
            m2_pin=M2_PIN,
            fault_pin=FAULT_PIN,
            steps_per_revolution=200,
            max_speed=1000,
            acceleration=500,
        )
        stepper.setup()
        stepper.set_microstepping_mode(GPIO_Lib.Stepper.MICROSTEPS.X1_32)
        stepper.configure_motion_rev(
            steps_per_rev=200,
            max_speed_rpm=30.0,
            max_accel_rpm_s=60.0,
        )

        print("Moving to 0.5 rev …")
        stepper.set_current_position_rev(0.0)
        stepper.move_to_position_rev(0.5, speed_override_rpm=20.0, accel_override_rpm_s=40.0)
        _poll_until_stopped(stepper)

        print("Moving back to origin …")
        stepper.move_to_position_rev(0.0, speed_override_rpm=20.0, accel_override_rpm_s=40.0)
        _poll_until_stopped(stepper)

        print("Decelerating stop test …")
        stepper.move_to_position_rev(1.0, speed_override_rpm=24.0, accel_override_rpm_s=48.0)
        time.sleep(0.3)
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
