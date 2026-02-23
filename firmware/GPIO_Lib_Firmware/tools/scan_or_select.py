#!/usr/bin/env python3
"""Device scanner and configurator for PlatformIO.

This script lives under the firmware tree, so we need to ensure the
workspace root is on ``sys.path`` before importing the host library
package (`px_device_interfaces`).  When the file is executed directly
(e.g. via ``python tools/scan_or_select.py``) the current working
directory is usually the firmware folder which is one level too deep.
"""

import sys
import os

# ensure host package is importable (debug)
_workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
# insert workspace root into path so host package can be found
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

import sys
import serial
import serial.tools.list_ports
import struct
import time
import os
import json
import argparse

# host library imports (workspace root added above)
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib

# Protocol constants
CMD_FIRMWARE_BUILD_FLAGS = 0xFFFD
CMD_FIRMWARE_INFO = 0xFFFE
CMD_FIRMWARE_VERSION = 0xFFFF

# Baud rates to try (in order)
BAUD_RATES = [921600, 115200, 9600]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INI_PATH = os.path.join(ROOT, 'platformio.ini')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'device_board_info.json')

# Known ports to scan first
known_ports = [
    '/dev/ttyACM0',
    '/dev/ttyACM1',
    '/dev/ttyUSB0',
    '/dev/ttyUSB1',
    'COM3',
    'COM4',
]

# Build flags to add for device configuration
build_flag_list = [
    'DEBUG',
    'FASTLED',
    'I2C',
    'SPI',
    'UART',
    'LCD',
    'IPS',
    'TOUCHSCREEN',
    'WIFI',
    'BLUETOOTH',
    'SD_CARD',
    'OLED',
    'RESET_DEVICE',
]


def load_board_config() -> dict:
    """Load board configuration from device_board_info.json."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading board config: {e}")
        return {}

def get_firmware_info(port: str) -> tuple[tuple[int, int, int], str, list[str]]:
    """Get firmware version, name, and build flags using GPIO_Lib API."""
    cfg = USBTransportConfig(port=port, baud=921600, debug=False, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)
    gpio.setHandshakeEnabled(True)
    try:
        gpio.start()
        gpio.requestFirmwareInfo()
    finally:
        gpio.stop()
    return gpio.firmware_version, gpio.firmware_name, gpio.firmware_build_flags


def extract_board_flag(build_flags: list[str]) -> str | None:
    """Extract BOARD=... from build flags."""
    for token in build_flags:
        if token.upper().startswith('BOARD='):
            return token.split('=', 1)[1]
    return None


def normalize_flags_for_display(build_flags) -> list[str]:
    """Convert build flags (string or list) to simple display names.

    The firmware returns a list of tokens split by spaces; each token may
    include a '-D' prefix and/or a '_SUPPORT' suffix.  Items containing an
    '=' (e.g. BOARD=...) are ignored.  The result is a list of unique
    flag names suitable for showing to the user.
    """
    # accept either a whitespace-separated string or a list of strings
    if isinstance(build_flags, str):
        tokens = build_flags.split()
    else:
        tokens = list(build_flags or [])

    flags: list[str] = []
    for token in tokens:
        if '=' in token:
            continue
        flag = token[2:] if token.startswith('-D') else token
        flag = flag.replace('_SUPPORT', '')
        if flag and flag not in flags:
            flags.append(flag)
    return flags


def format_flags_for_ini(flags: list[str]) -> list[str]:
    """Convert to INI format (add -D and _SUPPORT)."""
    result = []
    for flag in flags:
        if flag == 'DEBUG':
            result.append('-DDEBUG')
        elif flag != 'GPIO':
            result.append(f'-D{flag}_SUPPORT')
    return result


def scan_known_ports(ports_list) -> list[dict]:
    """Scan ports for devices."""
    detected = []
    board_config = load_board_config()
    
    for port in ports_list:
        for baud in BAUD_RATES:
            try:
                print(f"Scanning {port} @ {baud}... ", flush=True)
                version, name, flags = get_firmware_info(port)
                board_id = extract_board_flag(flags)
                
                if not board_id:
                    print(f"[unknown board] Version: {version} | Name: {name} | Flags: {flags}")
                    continue
                if board_id not in board_config:
                    print(f"[unrecognized board: {board_id}] Version: {version} | Name: {name} | Flags: {flags}")
                    continue
                
                config = board_config[board_id]
                print(f"[OK] {config['manufacturer']} / {config['model']}")
                
                detected.append({
                    'port': port,
                    'baud': baud,
                    'firmware_version': version,
                    'firmware_name': name,
                    'build_flags': flags,
                    'board_id': board_id,
                    'config': config,
                })
                break
                    
            except Exception as e:
                print(f"Error scanning port {port} @ {baud}: {e}")
                continue
    
    return detected


import select


def ask(prompt: str, timeout: float | None = 2) -> str:
    """Prompt user and optionally time‑out if no input.

    ``timeout`` is a number of seconds to wait for a line.  When it elapses
    an empty string is returned.  Passing ``None`` behaves the same as
    ``sys.stdin.readline()`` and will block indefinitely.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if timeout is None:
        line = sys.stdin.readline()
    else:
        # select on stdin file descriptor; works on Unix terminals
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return ''
        line = sys.stdin.readline()
    return (line or '').rstrip('\n')


def edit_build_flags(current_flags) -> list[str]:
    """Interactive flag editor.

    ``current_flags`` may be a string or list; we always return a list of
    display names representing the selected items.
    """
    selected = set(normalize_flags_for_display(current_flags))
    
    while True:
        print("\nBuild flags ([X] = selected):")
        for i, flag in enumerate(build_flag_list):
            mark = "X" if flag in selected else " "
            print(f"  [{i}] [{mark}] {flag}")
        
        s = ask("Toggle (numbers), 'a'=all, 'c'=clear, Enter=done: \n").strip()
        
        if not s:
            break
        elif s.lower() == 'c':
            selected.clear()
        elif s.lower() == 'a':
            if len(selected) == len(build_flag_list):
                selected.clear()
            else:
                selected.update(build_flag_list)
        else:
            for part in s.split():
                try:
                    idx = int(part)
                    if 0 <= idx < len(build_flag_list):
                        flag = build_flag_list[idx]
                        if flag in selected:
                            selected.remove(flag)
                        else:
                            selected.add(flag)
                except ValueError:
                    pass
    
    return list(selected)


def update_platformio_ini(device: dict) -> bool:
    """Write platformio.ini."""
    config = device['config']
    board_id = device['board_id']
    port = device['port']
    
    device_flags = normalize_flags_for_display(device['build_flags'])
    formatted_flags = format_flags_for_ini(device_flags)
    
    if 'device_based_flags' in config:
        formatted_flags = config['device_based_flags'] + formatted_flags
    
    all_flags = [f'-DBOARD={board_id}'] + formatted_flags
    build_flags_str = ' '.join(all_flags)
    
    try:
        # Check if PIO_INTERACTIVE was already set in existing INI (preserve its state)
        existing_pio_interactive = None
        if os.path.isfile(INI_PATH):
            try:
                with open(INI_PATH, 'r') as f:
                    for line in f:
                        line_stripped = line.strip()
                        if line_stripped.startswith('PIO_INTERACTIVE') and '=' in line_stripped:
                            existing_pio_interactive = line_stripped
                            break
            except Exception:
                pass
        
        lines = [
            '[platformio]',
            'default_envs = device',
            '',
            '[env]',
            'extra_scripts = pre:tools/pio_pre_hook.py, post:tools/pio_post_hook.py',
            'lib_deps =',
            '\tadafruit/Adafruit GFX Library@^1.11.9',
            '\tadafruit/Adafruit ST7735 and ST7789 Library@^1.9.3',
            'lib_extra_dirs = lib',
            '',
            '[env:device]',
            f'platform = {config["platform"]}',
            f'board = {config["board"]}',
            f'framework = {config["framework"]}',
            f'upload_port = {port}',
            f'upload_speed = {config["upload_speed"]}',
            f'monitor_speed = {config["monitor_speed"]}',
            f'build_flags = {build_flags_str}',
            '',
            '# Uncomment the line below to run in interactive mode (allows editing build flags during build)',
        ]
        
        # Preserve existing PIO_INTERACTIVE setting (commented or uncommented)
        if existing_pio_interactive:
            lines.append(existing_pio_interactive)
        else:
            lines.append('# PIO_INTERACTIVE = 1')
        
        with open(INI_PATH, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        
        print(f"\nConfigured {config['manufacturer']} / {config['model']} on {port}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Detect and configure GPIO_Lib devices.')
    parser.add_argument('-i', '--interactive', action='store_true', help='Force interactive mode')
    args = parser.parse_args()

    print("Scanning for devices...")
    detected = scan_known_ports(known_ports)

    if not detected:
        print("\nError: No devices found.")
        return 1

    if len(detected) > 1 or args.interactive:
        print(f"\nFound {len(detected)} device(s):")
        for i, dev in enumerate(detected):
            cfg = dev['config']
            print(f"  [{i}] {cfg['manufacturer']} / {cfg['model']} on {dev['port']}")
        
        if len(detected) > 1:
            s = ask("\nSelect device: ").strip()
            try:
                device = detected[int(s)]
            except (ValueError, IndexError):
                print("Invalid selection.")
                return 1
        else:
            device = detected[0]
        
        if args.interactive:
            # user editing returns a list of display names; just store that
            flags = edit_build_flags(device['build_flags'])
            device['build_flags'] = flags
    else:
        device = detected[0]

    cfg = device['config']
    print(f"\nConfiguring {cfg['manufacturer']} / {cfg['model']} on {device['port']}")
    
    return 0 if update_platformio_ini(device) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
