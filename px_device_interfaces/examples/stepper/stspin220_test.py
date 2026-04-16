"""STSPIN220 stepper driver smoke test.

Usage::

    # Real hardware
    python -m px_device_interfaces.examples.stepper.stspin220_test --port /dev/ttyACM0

    # Offline (no hardware needed)
    python -m px_device_interfaces.examples.stepper.stspin220_test --mock

Edit the PIN constants below to match your wiring.
"""
import argparse
import time
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt

from px_device_interfaces.GPIO_Lib import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.transports.mock import MockTransportConfig

# ── Stepper pin assignments ───────────────────────────────────────────────────
STEP_PIN  = 2
DIR_PIN   = 3
EN_PIN    = 4
M0_PIN    = 5
M1_PIN    = 6
SLP_PIN   = 7
FAULT_PIN = 10

# ── Encoder pin assignments (STM32duino: PA0=0, PA1=1) ───────────────────────
ENC_PIN_A = 0   # PA0
ENC_PIN_B = 1   # PA1
ENC_PPR   = 600  # 600 CPR encoder (600 A-channel pulses/rev); quadrature edges /4 = 600 user counts/rev


# Samples: list of (elapsed_s, stepper_position, encoder_position)
_Sample = Tuple[float, int, int]


def _poll_until_stopped(
    stepper,
    encoder=None,
    label: str = "",
    t0: float = 0.0,
    samples: Optional[List[_Sample]] = None,
    max_polls: int = 200,
) -> None:
    """Poll stepper status (and optional encoder) until motion stops."""
    if samples is None:
        samples = []
    consecutive_failures = 0
    for _ in range(max_polls):
        try:
            status = stepper.get_status(timeout=0.35, retries=2, retry_delay=0.01)
        except RuntimeError:
            consecutive_failures += 1
            if consecutive_failures >= 25:
                raise
            time.sleep(0.05)
            continue

        consecutive_failures = 0
        enc_pos = 0
        if encoder is not None:
            try:
                enc_data = encoder.read(timeout=0.2)
                enc_pos = enc_data["revolutions"] * ENC_PPR + enc_data["position"]
            except RuntimeError:
                enc_pos = 0
        t = time.time() - t0
        samples.append((t, status.get("position_steps", 0), enc_pos))
        # Use numeric state_code when available to highlight homing
        state_code = status.get("state_code")
        moving = bool(status.get("moving", False))
        state_flag = (
            "HOM" if state_code == GPIO_Lib.Stepper.STATUS_HOMING else ("MOV" if moving else "IDL")
        )
        print(
            f"  [{label}]  state={status['state']:<12s} pos={status['position']:8.3f} {status['unit_mode']:<3s}  "
            f"steps={status.get('position_steps', 0):+8d}  enc={enc_pos:+8d}  {state_flag}",
            end="\r",
            flush=True,
        )
        if not status["moving"]:
            break
        time.sleep(0.1)
    print()


def _plot(samples: List[_Sample], has_encoder: bool) -> None:
    if not samples:
        return
    ts   = [s[0] for s in samples]
    spos = [s[1] for s in samples]
    epos = [s[2] for s in samples]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Stepper position (steps)", color="tab:blue")
    ax1.plot(ts, spos, color="tab:blue", linewidth=1.5, label="Stepper (steps)")
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    if has_encoder:
        ax2 = ax1.twinx()
        ax2.set_ylabel("Encoder position (counts)", color="tab:orange")
        ax2.plot(ts, epos, color="tab:orange", linewidth=1.5, linestyle="--", label="Encoder (counts)")
        ax2.tick_params(axis="y", labelcolor="tab:orange")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    else:
        ax1.legend(loc="upper left")

    ax1.set_title("STSPIN220 — Stepper vs Encoder position over time")
    ax1.grid(True, linestyle=":", alpha=0.6)
    fig.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="STSPIN220 stepper smoke test")
    parser.add_argument("--mock", action="store_true",
                        help="Use MockTransport (no hardware needed)")
    parser.add_argument("--port", default=None, help="Serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--allow-microstep-mismatch",
        action="store_true",
        help="Continue the test even if encoder verification shows the configured microstep mode did not latch",
    )
    args = parser.parse_args()

    if args.mock:
        gpio = GPIO_Lib(transport_config=MockTransportConfig())
        print("[MockTransport] offline mode — commands sent to /dev/null.")
    else:
        cfg = USBTransportConfig(port=args.port, auto_connect=True, debug=args.debug)
        gpio = GPIO_Lib(transport_config=cfg)

    encoder = None
    all_samples: List[_Sample] = []

    try:
        gpio.start()
        if not args.mock:
            time.sleep(0.5)

        # ── Encoder setup ─────────────────────────────────────────────────────
        ENCODER_ENABLED = True
        if not args.mock and ENCODER_ENABLED:
            encoder = gpio.Encoder(
                gpio_lib=gpio,
                pin_a=ENC_PIN_A,
                pin_b=ENC_PIN_B,
                ppr=ENC_PPR,
            )
            encoder.setup()
            gpio.await_send_empty()
            time.sleep(0.1)

        # ── Stepper setup ─────────────────────────────────────────────────────
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
            max_speed=500000,
            acceleration=800000,
        )
        stepper.setup()
        stepper.set_microstepping_mode(GPIO_Lib.Stepper.MICROSTEPS.X1_64)
        stepper.initialize()
        stepper.configure_motion_mm(
            steps_per_mm=100.0,
            max_speed_mm_s=100.0,
            max_accel_mm_s2=50.0,
        )
        gpio.await_send_empty()
        time.sleep(0.1)

        if not args.mock and encoder is not None:
            print("Verifying microstepping mode …")
            verification = stepper.verify_microstepping(
                encoder=encoder,
                test_steps=200,
                speed=500,
                move_timeout=10.0,
                fail_loud=not args.allow_microstep_mismatch,
            )
            print(f"  Encoder counts for 200 steps: {verification['encoder_counts']:+d}")
            print(f"  Expected at  1/1 (full): ~{verification['expected_counts_full_step']:4d} counts")
            print(f"  Expected at 1/{stepper.microstep_div}:        ~{verification['expected_counts_at_configured_divisor']:.2f} counts")
            print(
                f"  Detected microstep divisor: ~{verification['detected_divisor_float']:.2f} "
                f"(rounded: {verification['detected_divisor']}, set: {stepper.microstep_div})"
            )
            if verification["matches_configured_divisor"]:
                print(
                    f"  Microstepping OK: count error {verification['count_error']:.2f} "
                    f"within tolerance {verification['count_tolerance']:.2f}"
                )
            else:
                print("  WARNING: microstep latch did not take effect — check M0/M1/SLP pin wiring!")

        if encoder is not None:
            print("Auto-orienting encoder direction …")
            orientation = stepper.auto_orient_encoder(
                encoder=encoder,
                test_steps=50,
                speed=4000,
                move_timeout=10.0,
            )
            if orientation["flipped"]:
                print(f"  Encoder went {orientation['encoder_counts']:+d} — flipping direction.")
            else:
                print(f"  Encoder went {orientation['encoder_counts']:+d} — direction OK.")

        t0 = time.time()

        print("Moving to 0.25 rev …")
        stepper.configure_motion_rev(
            steps_per_rev=200,
            max_speed_rpm=24.0,
            max_accel_rpm_s=48.0,
        )
        gpio.await_send_empty()
        stepper.set_current_position_rev(0.0)
        stepper.move_to_position_rev(-1.5, speed_override_rpm=60.0, accel_override_rpm_s=300.0)
        _poll_until_stopped(stepper, encoder=encoder, label="0.25rev", t0=t0, samples=all_samples)

        print("Returning to 0 rev …")
        stepper.move_to_position_rev(0.0, speed_override_rpm=120.0, accel_override_rpm_s=600.0)
        _poll_until_stopped(stepper, encoder=encoder, label="0rev", t0=t0, samples=all_samples)

        stepper.configure_motion_mm(
            steps_per_mm=100.0,
            max_speed_mm_s=100.0,
            max_accel_mm_s2=100.0,
        )
        gpio.await_send_empty()

        print("Moving to 25 mm …")
        stepper.move_to_position_mm(20.0, speed=20.0, acceleration=25.0)
        _poll_until_stopped(stepper, encoder=encoder, label="25mm", t0=t0, samples=all_samples)

        # print("Setting current position to 100 mm …")
        # stepper.set_current_position_mm(100.0)
        # status = stepper.get_status()
        # print(f"  Current position after set: {status['position']:.3f} {status['unit_mode']}")

        print("Returning to 0 mm …")
        stepper.move_to_position_mm(0.0, speed=60.0, acceleration=150.0)
        _poll_until_stopped(stepper, encoder=encoder, label="0mm", t0=t0, samples=all_samples)

        if encoder is not None:
            try:
                enc_data = encoder.read(timeout=0.3)
                enc_pos = enc_data["revolutions"] * ENC_PPR + enc_data["position"]
            except Exception:
                enc_pos = 0
        else:
            enc_pos = 0

        status = stepper.get_status()
        all_samples.append((time.time() - t0, status.get("position_steps", 0), enc_pos))
        print(
            f"Final: state={status['state']}  pos={status['position']:.3f} {status['unit_mode']}  "
            f"steps={status.get('position_steps', 0):+d}  enc={enc_pos:+d}  fault_flags=0x{status['fault_flags']:02X}"
        )
        stepper.stop(immediate=True)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        gpio.stop()

    _plot(all_samples, has_encoder=(encoder is not None))


if __name__ == "__main__":
    main()
