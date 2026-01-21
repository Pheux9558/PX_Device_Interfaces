#!/usr/bin/env python3
"""Manual USB smoke-test for connecting to a device.

This script is intentionally outside `python/tools/` so it won't be
executed by the automated test runner. Run it manually when you have a
USB device connected.

Examples:
  python3 scripts/stest_usb.py --port /dev/ttyUSB0 --baud 115200 --send "M100"
  python3 scripts/stest_usb.py --port /dev/ttyUSB0 --baud 115200 --interactive
  
  # Set Pin 2 to output high
  python3 scripts/stest_usb.py --port /dev/ttyUSB0 --baud 115200 --send "M2 N2; P2 N2 V1"

The script uses the transports factory to create a `USB` transport and
performs a simple connect/send/receive flow.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual USB smoke-test using transports factory")
    parser.add_argument("--port", required=True, help="Serial port (e.g. /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--timeout", type=float, default=0.5, help="Receive timeout (s)")
    parser.add_argument("--send", help="Send a single message and exit")
    parser.add_argument("--interactive", action="store_true", help="Open an interactive send loop")
    args = parser.parse_args()

    # ensure repo root is on sys.path so we can import the package
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    try:
        from python.transports import create_transport_for_device
    except Exception as e:
        print("Failed to import transports factory:", e)
        return 2

    # create a temporary settings object for this test run
    from python.settings_manager import Settings, save_connection_settings

    tmp_name = "__stest_tmp__"
    s = Settings(program="Connection_Organiser", device=tmp_name, data={"type": "USB", "port": args.port, "baud": args.baud, "timeout": args.timeout})
    save_connection_settings(tmp_name, s)
    try:
        t = create_transport_for_device(tmp_name)
    finally:
        # leave the settings file for debugging; caller may remove it
        pass

    print(f"Connecting to {args.port} at {args.baud}...", end=" ")
    ok = False
    try:
        ok = t.connect()
    except Exception as e:
        print("error:", e)

    if not ok and not t.is_connected:
        print("FAILED to connect")
        return 3
    print("OK")
    
    # give device a moment to settle
    time.sleep(1)

    try:
        if args.send:
            print("Sending:", args.send)
            t.send(args.send + "\n")
            # give device a moment to respond
            time.sleep(0.05)
            resp = t.receive(timeout=args.timeout)
            print("Response:", repr(resp))
        elif args.interactive:
            print("Entering interactive mode. Type a line to send, Ctrl-C to exit.")
            while True:
                try:
                    line = input("> ")
                except EOFError:
                    break
                if not line:
                    continue
                t.send(line + "\n")
                time.sleep(0.1)
                resp = t.receive(timeout=args.timeout)
                print("<-", repr(resp))
        else:
            print("No --send or --interactive specified; nothing to do.")
    finally:
        try:
            t.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
