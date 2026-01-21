#!/usr/bin/env python3
"""Test and demo entry point for `settings_manager`.

Features:
- list devices
- load device settings
- interactively create/edit and save settings
- optionally attempt a ConnectionOrganiser connect (prompted)

Usage examples:
    python3 python/tools/test_settings_manager.py --list
    python3 python/tools/test_settings_manager.py --load temp

"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from pathlib import Path
import sys

# Ensure the package root (the `python/` folder) is on sys.path so this script can be
# run directly (e.g. `python3 python/tools/test_settings_manager.py`) as well as
# imported as a package.
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from px_device_interfaces.settings_manager import (
    list_devices,
    load_connection_settings,
    save_connection_settings,
    Settings,
    interactive_edit,
)


# interactive_edit now lives in `python.settings_manager` and is imported above


def cmd_list(args: argparse.Namespace) -> None:
    devs = list_devices()
    if not devs:
        print("No devices found under python/sys_files/Connection_Organiser/")
        return
    print("Devices:")
    for d in devs:
        print(f" - {d}")


def cmd_load(args: argparse.Namespace) -> None:
    name = args.device
    if not name:
        print("Please pass a device name with --device <name>")
        return
    s = load_connection_settings(name)
    print(json.dumps(s.to_dict(), indent=2))
    if args.edit:
        s2 = interactive_edit(s)
        save_connection_settings(name, s2)
        print("Saved:")
        print(json.dumps(s2.to_dict(), indent=2))


def attempt_connect(name: str) -> None:
    try:
        from python import connection_organiser_with_opc as conorg
    except Exception as e:
        print(f"Cannot import ConnectionOrganiser: {e}")
        return
    print(f"Attempting connection for device '{name}' (this may fail if no hardware/server)")
    co = conorg.ConnectionOrganiser(device_name=name, init_connect=True, debug=True)
    print(f"Connected: {co.connected}")
    if co.connected:
        co.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    # legacy migration removed; this script is JSON-first
    parser.add_argument("--load", dest="device", help="Load device settings by name")
    parser.add_argument("--edit", action="store_true", help="Edit and save when loading")
    parser.add_argument("--connect", action="store_true", help="Attempt a real connection after load (unsafe)")
    args = parser.parse_args()

    if args.list:
        cmd_list(args)
        return
    # no migrate option
    if args.device:
        cmd_load(args)
        if args.connect:
            attempt_connect(args.device)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
