#!/usr/bin/env python3
"""Device scanner and configurator for PlatformIO.

Scans serial ports for GPIO_Lib firmware devices, detects device type via BOARD flag,
and configures platformio.ini with appropriate settings.

Usage:
  python scan_or_select.py              # Auto-detect and configure (non-interactive)
  python scan_or_select.py -i           # Interactive mode (prompt user)
  python scan_or_select.py --force      # Force reconfiguration
"""

import sys
import serial
import serial.tools.list_ports
import struct
import time
import os
import json
import argparse

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


def send_command(ser: serial.Serial, cmd: int, payload: bytes = b'') -> tuple[int, bytes]:
    """Send a framed command and read a framed response.
    
    Framing: [0xAA][CMD(2)][LEN(2)][PAYLOAD...][CHK]
    CHK = (CMD + LEN + sum(PAYLOAD)) & 0xFF
    """
    start = bytes([0xAA])
    cmd_bytes = int(cmd).to_bytes(2, "little")
    len_bytes = int(len(payload)).to_bytes(2, "little")
    chk = (cmd + len(payload) + sum(payload)) & 0xFF
    packet = start + cmd_bytes + len_bytes + payload + bytes([chk])

    ser.write(packet)
    ser.flush()

    while True:
        b = ser.read(1)
        if not b:
            raise RuntimeError("No response from device")
        if b[0] == 0xAA:
            break

    header = ser.read(4)
    if len(header) < 4:
        raise RuntimeError("Incomplete header")
    resp_cmd, resp_len = struct.unpack('<HH', header)

    MAX_PAYLOAD = 64 * 1024
    if resp_len > MAX_PAYLOAD:
        raise RuntimeError(f"Payload too large: {resp_len}")

    resp_payload = b''
    while len(resp_payload) < resp_len:
        chunk = ser.read(resp_len - len(resp_payload))
        if not chunk:
            raise RuntimeError("Incomplete payload")
        resp_payload += chunk

    chk_b = ser.read(1)
    if not chk_b:
        raise RuntimeError("No checksum")
    
    if ((resp_cmd + resp_len + sum(resp_payload)) & 0xFF) != chk_b[0]:
        raise RuntimeError("Checksum mismatch")

    return resp_cmd, resp_payload


def get_firmware_info(ser: serial.Serial) -> tuple[tuple[int, int, int], str, str]:
    """Get firmware version, info, and build flags."""
    resp_cmd, data = send_command(ser, CMD_FIRMWARE_VERSION)
    if resp_cmd != CMD_FIRMWARE_VERSION or len(data) != 3:
        raise RuntimeError("Bad version response")
    major, minor, patch = struct.unpack('<BBB', data)
    
    resp_cmd, data = send_command(ser, CMD_FIRMWARE_INFO)
    if resp_cmd != CMD_FIRMWARE_INFO:
        raise RuntimeError("Bad info response")
    info = data.decode('utf-8', errors='replace')
    
    resp_cmd, data = send_command(ser, CMD_FIRMWARE_BUILD_FLAGS)
    if resp_cmd != CMD_FIRMWARE_BUILD_FLAGS:
        raise RuntimeError("Bad flags response")
    flags = data.decode('utf-8', errors='replace')
    
    return (major, minor, patch), info, flags


def extract_board_flag(build_flags: str) -> str | None:
    """Extract BOARD=... from build flags."""
    for token in build_flags.split():
        if token.upper().startswith('BOARD='):
            return token.split('=', 1)[1]
    return None


def normalize_flags_for_display(build_flags_str: str) -> list[str]:
    """Convert to display names (remove -D and _SUPPORT)."""
    flags = []
    for token in build_flags_str.split():
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
                print(f"Scanning {port} @ {baud}... ", end="", flush=True)
                with serial.Serial(port, baudrate=baud, timeout=1) as ser:
                    time.sleep(0.5)
                    version, info, flags = get_firmware_info(ser)
                    board_id = extract_board_flag(flags)
                    
                    if not board_id or board_id not in board_config:
                        print(f"[skip]")
                        continue
                    
                    config = board_config[board_id]
                    print(f"[OK] {config['manufacturer']} / {config['model']}")
                    
                    detected.append({
                        'port': port,
                        'baud': baud,
                        'firmware_version': version,
                        'firmware_info': info,
                        'build_flags': flags,
                        'board_id': board_id,
                        'config': config,
                    })
                    break
                    
            except Exception:
                continue
    
    return detected


def ask(prompt: str) -> str:
    """Prompt user."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return (sys.stdin.readline() or '').rstrip('\n')


def edit_build_flags(current_flags: str) -> str:
    """Interactive flag editor."""
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
    
    return ' '.join(selected)


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
            flags = edit_build_flags(device['build_flags'])
            device['build_flags'] = ' '.join(f + '_SUPPORT' if f not in ['DEBUG', 'GPIO'] else f for f in flags.split())
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
