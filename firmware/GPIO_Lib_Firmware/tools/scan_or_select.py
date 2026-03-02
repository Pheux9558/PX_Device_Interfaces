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

# unbuffer output by setting PYTHONUNBUFFERED and flushing after each write
os.environ['PYTHONUNBUFFERED'] = '1'

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
import subprocess

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

# Build flags to add for device configuration
build_flag_list = [
    'DEBUG',
    'FASTLED',
    'I2C',
    'SPI',
    'UART',
    'LCD',
    'HD44780',
    'AIP31068L',
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
        print(f"Error loading board config: {e}", flush=True)
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
        if not gpio.firmware_version:
            raise Exception("Failed to get firmware version (no response)")
        if not gpio.firmware_name:
            raise Exception("Failed to get firmware name (no response)")
        if not gpio.firmware_build_flags:
            raise Exception("Failed to get firmware build flags (no response)")
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


def scan_known_ports() -> list[dict]:
    """Scan available ports with descriptions for devices."""
    detected = []
    board_config = load_board_config()
    
    # Get all available ports with descriptions
    available_ports = serial.tools.list_ports.comports()
    
    for port_info in available_ports:
        # Only scan ports that have a description (likely USB devices)
        if not port_info.description or port_info.description == 'n/a':
            continue
        
        port = port_info.device
        for baud in BAUD_RATES:
            try:
                print(f"Scanning {port} ({port_info.description}) @ {baud}... ", flush=True)
                version, name, flags = get_firmware_info(port)
                board_id = extract_board_flag(flags)
                
                if not board_id:
                    print(f"[unknown board] Version: {version} | Name: {name} | Flags: {flags}", flush=True)
                    continue
                if board_id not in board_config:
                    print(f"[unrecognized board: {board_id}] Version: {version} | Name: {name} | Flags: {flags}", flush=True)
                    continue
                
                config = board_config[board_id]
                print(f"[OK] {config['manufacturer']} / {config['model']}", flush=True)
                
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
                print(f"Error scanning port {port} @ {baud}: {e}", flush=True)
                continue
    
    return detected


import select


def ask(prompt: str, timeout: float | None = 5) -> str:
    """Prompt user and optionally time‑out if no input.

    ``timeout`` is a number of seconds to wait for a line.  When it elapses
    an empty string is returned.  Passing ``None`` behaves the same as
    ``sys.stdin.readline()`` and will block indefinitely.
    """
    sys.stdout.write(prompt + "\n")
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
        print("\nBuild flags ([X] = selected):", flush=True)
        for i, flag in enumerate(build_flag_list):
            mark = "X" if flag in selected else " "
            print(f"  [{i}] [{mark}] {flag}", flush=True)
        
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
    
    # Filter device_based_flags to only include ones compatible with enabled modules
    if 'device_based_flags' in config:
        filtered_device_flags = []
        for flag in config['device_based_flags']:
            # Check if this flag depends on a module being enabled
            # DEBUG_FASTLED_* flags require FASTLED_SUPPORT
            if 'DEBUG_FASTLED_' in flag:
                if 'FASTLED' in device_flags:
                    filtered_device_flags.append(flag)
            else:
                # All other device flags are always included
                filtered_device_flags.append(flag)
        formatted_flags = filtered_device_flags + formatted_flags
    
    all_flags = [f'\n\t-DBOARD={board_id}'] + formatted_flags
    build_flags_str = '\n\t'.join(all_flags)
    
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
        
        # Conditionally add display libraries based on enabled flags
        lib_deps = []
        
        # TFT displays (ST7735/ST7789) require GFX and ST7735 libraries
        if 'LCD' in device_flags or 'IPS' in device_flags:
            if 'adafruit/Adafruit GFX Library@^1.11.9' not in lib_deps:
                lib_deps.append('adafruit/Adafruit GFX Library@^1.11.9')
            lib_deps.append('adafruit/Adafruit ST7735 and ST7789 Library@^1.9.3')
        
        # OLED displays (SSD1306) require GFX and SSD1306 libraries
        if 'OLED' in device_flags:
            if 'adafruit/Adafruit GFX Library@^1.11.9' not in lib_deps:
                lib_deps.append('adafruit/Adafruit GFX Library@^1.11.9')
            lib_deps.append('adafruit/Adafruit SSD1306@^2.5.7')
        
        # Character LCDs (HD44780, AiP31068L) require LiquidCrystal_I2C
        if 'HD44780' in device_flags or 'AIP31068L' in device_flags:
            lib_deps.append('marcoschwartz/LiquidCrystal_I2C@^1.1.4')
        
        # FastLED WS2812 requires Adafruit_NeoPixel
        if 'FASTLED' in device_flags:
            lib_deps.append('adafruit/Adafruit NeoPixel@^1.10.0')
        
        # Build lib_deps lines for INI file
        lib_deps_lines = []
        if lib_deps:
            lib_deps_lines = ['lib_deps ='] + [f'\t{lib}' for lib in lib_deps]
        
        lines = [
            '[platformio]',
            'default_envs = device',
            '',
            '[env]',
            'extra_scripts = pre:tools/pio_pre_hook.py, post:tools/pio_post_hook.py',
        ]
        
        # Add lib_deps only if display libraries are needed
        if lib_deps_lines:
            lines.extend(lib_deps_lines)
        
        lines.extend([
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
        ])
        
        # Preserve existing PIO_INTERACTIVE setting (commented or uncommented)
        if existing_pio_interactive:
            lines.append(existing_pio_interactive)
        else:
            lines.append('# PIO_INTERACTIVE = 1')
        
        with open(INI_PATH, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        
        print(f"\nConfigured {config['manufacturer']} / {config['model']} on {port}", flush=True)
        
        # Force clean build to remove old object files compiled with previous flags
        # This is critical when disabling features - old objects would still have those flags
        print("Cleaning build artifacts to apply new flags...", flush=True)
        try:
            # Run pio clean to remove .pio/build directory
            subprocess.check_call(['pio', 'run', '-t', 'clean'], cwd=ROOT, 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Clean completed.", flush=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Clean failed ({e}), continuing anyway...", flush=True)
        except FileNotFoundError:
            print("Warning: 'pio' command not found, skipping clean...", flush=True)
        
        return True
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return False

def get_manufacturers_and_models(board_config: dict) -> dict:
    """Organize board config by manufacturer.
    
    Returns dict like:
    {
        "ESP32": [("T-Dongle-S3", "ESP32_T_DONGLE_S3"), ("Pico D4", "ESP32_Pico_D4"), ...],
        "Arduino": [...],
    }
    """
    by_mfg = {}
    for board_id, config in board_config.items():
        mfg = config.get('manufacturer', 'Unknown')
        model = config.get('model', 'Unknown')
        if mfg not in by_mfg:
            by_mfg[mfg] = []
        by_mfg[mfg].append((model, board_id))
    return by_mfg


def suggest_platform_for_manufacturer(mfg: str) -> dict | None:
    """Suggest common platforms for a manufacturer. Returns dict with platform suggestions."""
    suggestions = {
        'ESP32': {'platform': 'espressif32', 'framework': 'arduino', 'board': 'esp32dev'},
        'Arduino': {'platform': 'atmelavr', 'framework': 'arduino', 'board': 'uno'},
        'STM32': {'platform': 'ststm32', 'framework': 'arduino', 'board': 'nucleo_f401re'},
        'RP2040': {'platform': 'raspberrypi', 'framework': 'arduino', 'board': 'pico'},
    }
    return suggestions.get(mfg)


def parse_device_based_flags(flag_input: str) -> list[str]:
    """Parse comma or space-separated flag input into a list of valid flag strings."""
    if not flag_input.strip():
        return []
    # Split by comma or space
    parts = [s.strip() for s in flag_input.replace(',', ' ').split()]
    # Filter out empty strings
    return [p for p in parts if p]


def generate_board_id(manufacturer: str, model: str) -> str:
    """Generate a board ID from manufacturer and model.
    
    Example: "ESP32" + "My Board" → "ESP32_My_Board"
    """
    # Replace spaces with underscores, remove special chars, uppercase
    mfg_part = manufacturer.upper().replace(' ', '_').replace('-', '_')
    model_part = model.upper().replace(' ', '_').replace('-', '_')
    board_id = f"{mfg_part}_{model_part}"
    # Clean up multiple underscores
    while '__' in board_id:
        board_id = board_id.replace('__', '_')
    return board_id


def create_new_device_config() -> int:
    """Create a new device configuration entry in device_board_info.json.
    1) Prompt user for manufacturer and model name (list existing ones that can be selected or allow new entry)
    2) Prompt user for platform, board, framework, upload_speed, monitor_speed, and any device_based_flags (list existing ones that can be selected or allow new entry)
    3) Add new entry to device_board_info.json
    4) Update platformio.ini
    5) Return True if successful else False
    """
    board_config = load_board_config()
    by_mfg = get_manufacturers_and_models(board_config)
    
    # Step 1: Select or create manufacturer
    print("\n=== Create New Device Configuration ===", flush=True)
    print("\nExisting manufacturers:", flush=True)
    mfg_list = sorted(by_mfg.keys())
    for i, mfg in enumerate(mfg_list):
        print(f"  [{i}] {mfg}", flush=True)
    print(f"  [{len(mfg_list)}] Enter new manufacturer", flush=True)
    
    s = ask("Select manufacturer by index: ").strip()
    try:
        mfg_idx = int(s)
        if 0 <= mfg_idx < len(mfg_list):
            manufacturer = mfg_list[mfg_idx]
        elif mfg_idx == len(mfg_list):
            manufacturer = ask("Enter manufacturer name: ").strip()
            if not manufacturer:
                print("Manufacturer name cannot be empty.", flush=True)
                return 1
        else:
            print("Invalid index.", flush=True)
            return 1
    except ValueError:
        print("Invalid input.", flush=True)
        return 1
    
    # Step 2: Enter model name
    model = ask("Enter model name: ").strip()
    if not model:
        print("Model name cannot be empty.", flush=True)
        return 1
    
    # Auto-generate board ID
    board_id = generate_board_id(manufacturer, model)
    print(f"Generated board ID: {board_id}", flush=True)
    confirm = ask("Accept this board ID (y/N): ").strip().lower()
    if confirm != 'y':
        custom_id = ask("Enter custom board ID (or press Enter to keep auto-generated): ").strip()
        if custom_id:
            board_id = custom_id
        # if empty, keep auto-generated board_id
    
    # Step 3: Select or enter platform and board
    print("\nCommon platforms for this manufacturer:", flush=True)
    suggestion = suggest_platform_for_manufacturer(manufacturer)
    if suggestion:
        print(f"  Suggested: platform={suggestion['platform']}, board={suggestion['board']}", flush=True)
        use_suggestion = ask("Use suggested platform/board (Y/n): ").strip().lower()
        if use_suggestion != 'n':
            platform = suggestion['platform']
            board = suggestion['board']
            framework = suggestion['framework']
        else:
            platform = ask("Enter platform (e.g., espressif32, atmelavr): ").strip()
            board = ask("Enter board (e.g., esp32dev, uno): ").strip()
            framework = ask("Enter framework (default: arduino): ").strip() or 'arduino'
    else:
        platform = ask("Enter platform (e.g., espressif32, atmelavr): ").strip()
        board = ask("Enter board (e.g., esp32dev, uno): ").strip()
        framework = ask("Enter framework (default: arduino): ").strip() or 'arduino'
    
    if not platform or not board:
        print("Platform and board cannot be empty.", flush=True)
        return 1
    
    # Step 4: Upload and monitor speeds
    upload_speed = ask("Enter upload speed (default: 921600): ").strip() or '921600'
    monitor_speed = ask("Enter monitor speed (default: 921600): ").strip() or '921600'
    
    try:
        upload_speed = int(upload_speed)
        monitor_speed = int(monitor_speed)
    except ValueError:
        print("Upload and monitor speeds must be integers.", flush=True)
        return 1
    
    # Step 5: Device-based flags
    print("\nDevice-based flags examples:", flush=True)
    print("  -DDEBUG_LED_PIN=10", flush=True)
    print("  -DDEBUG_BRIGHTNESS=64", flush=True)
    print("  -DDEBUG_FASTLED_DATA_PIN=40", flush=True)
    print("  Leave blank for no device-based flags", flush=True)
    flags_input = ask("Enter device-based flags (comma or space-separated): ").strip()
    device_based_flags = parse_device_based_flags(flags_input)
    
    # Build new config entry
    new_config = {
        'manufacturer': manufacturer,
        'model': model,
        'platform': platform,
        'board': board,
        'upload_speed': upload_speed,
        'monitor_speed': monitor_speed,
        'framework': framework,
        'device_based_flags': device_based_flags,
    }
    
    # Add to board config and save
    board_config[board_id] = new_config
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(board_config, f, indent=2)
        print(f"\nAdded new device configuration: {board_id}", flush=True)
    except Exception as e:
        print(f"Error saving config: {e}", flush=True)
        return 1
    
    # Create a device dict for platformio.ini update (use /dev/ttyACM0 as default)
    device = {
        'port': '/dev/ttyACM0',  # will be updated if available
        'board_id': board_id,
        'config': new_config,
        'build_flags': device_based_flags,  # start with device-based flags only
    }
    
    if not update_platformio_ini(device):
        return 1
    
    print(f"\nConfigured {manufacturer} / {model} on {device['port']}", flush=True)
    return 0


def select_existing_device_from_config() -> int:
    """Select an existing device from device_board_info.json and update platformio.ini.
    1) List all manufacturers from device_board_info.json with an index number ([0], [1], etc.)
    2) Prompt the user to select a manufacturer by index
    3) List all models for the selected manufacturer with an index number
    4) Prompt the user to select a model by index
    5) Update platformio.ini with the selected device configuration
    6) Return True if successful else False
    """
    board_config = load_board_config()
    by_mfg = get_manufacturers_and_models(board_config)
    
    print("\n=== Select Device from Configuration ===", flush=True)
    
    # Step 1: List manufacturers
    print("\nManufacturers:", flush=True)
    mfg_list = sorted(by_mfg.keys())
    for i, mfg in enumerate(mfg_list):
        print(f"  [{i}] {mfg}", flush=True)
    
    # Step 2: Select manufacturer
    s = ask("Select manufacturer by index: ").strip()
    try:
        mfg_idx = int(s)
        if 0 <= mfg_idx < len(mfg_list):
            manufacturer = mfg_list[mfg_idx]
        else:
            print("Invalid index.", flush=True)
            return 1
    except ValueError:
        print("Invalid input.", flush=True)
        return 1
    
    # Step 3: List models for selected manufacturer
    print(f"\nModels for {manufacturer}:", flush=True)
    models = by_mfg[manufacturer]
    for i, (model_name, board_id) in enumerate(models):
        print(f"  [{i}] {model_name} ({board_id})", flush=True)
    
    # Step 4: Select model
    s = ask("Select model by index: ").strip()
    try:
        model_idx = int(s)
        if 0 <= model_idx < len(models):
            model_name, board_id = models[model_idx]
        else:
            print("Invalid index.", flush=True)
            return 1
    except ValueError:
        print("Invalid input.", flush=True)
        return 1
    
    # Get the full config for this board
    config = board_config[board_id]
    
    # Offer interactive flag editing
    print(f"\nSelected: {manufacturer} / {model_name}", flush=True)
    edit_flags = ask("Edit build flags interactively? (y/N): ").strip().lower()
    
    if edit_flags == 'y':
        # Start with device_based_flags for display
        initial_flags = normalize_flags_for_display(config.get('device_based_flags', []))
        flags = edit_build_flags(initial_flags)
    else:
        # Use device_based_flags as-is
        flags = config.get('device_based_flags', [])
    
    # Create device dict for platformio.ini update
    device = {
        'port': '/dev/ttyACM0',  # default port, user can edit platformio.ini manually if needed
        'board_id': board_id,
        'config': config,
        'build_flags': flags,
    }
    
    if not update_platformio_ini(device):
        return 1
    
    print(f"\nConfigured {config['manufacturer']} / {config['model']} on {device['port']}", flush=True)
    return 0

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Detect and configure GPIO_Lib devices.')
    parser.add_argument('-i', '--interactive', action='store_true', help='Force interactive mode')
    parser.add_argument('--skip-prompts', action='store_true', help='Skip prompts if INI is already configured')
    args = parser.parse_args()

    # If skip-prompts is set and platformio.ini already has build_flags, exit successfully
    if args.skip_prompts and os.path.isfile(INI_PATH):
        try:
            with open(INI_PATH, 'r') as f:
                content = f.read()
                if 'build_flags' in content and '-DBOARD=' in content:
                    print("Platformio.ini already configured, skipping device scan.", flush=True)
                    return 0
        except Exception:
            pass

    print("Scanning for devices...", flush=True)
    detected = scan_known_ports()

    if not detected:
        print("\nError: No devices found.", flush=True)
        
        # If skip-prompts is set, exit with error instead of prompting
        if args.skip_prompts:
            print("No devices detected and --skip-prompts is set. Continuing with existing config.", flush=True)
            return 0
        
        # Ask user if they want to select a device from device_board_info.json even if it can't be detected or create a new entry (e.g. due to empty firmware or unsupported board)
        s = ask("Do you want to select a device from the config file or create a new entry? (y/N): ").strip().lower()
        if s == 'y':
            # ask if they want to select an existing device or create a new one
            s2 = ask("Select existing device (E) or create new entry (C)? (E/C): ").strip().lower()
            if s2 == 'e':
                return select_existing_device_from_config()
            elif s2 == 'c':
                return create_new_device_config()
            else:
                print("Invalid selection.", flush=True)
                return 1
        else:
            return 1

    if len(detected) > 1 or args.interactive:
        print(f"\nFound {len(detected)} device(s):", flush=True)
        for i, dev in enumerate(detected):
            cfg = dev['config']
            print(f"  [{i}] {cfg['manufacturer']} / {cfg['model']} on {dev['port']}", flush=True)
        
        if len(detected) > 1:
            s = ask("\nSelect device: ").strip()
            try:
                device = detected[int(s)]
            except (ValueError, IndexError):
                print("Invalid selection.", flush=True)
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
    print(f"\nConfiguring {cfg['manufacturer']} / {cfg['model']} on {device['port']}", flush=True)
    
    return 0 if update_platformio_ini(device) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", flush=True)
        sys.exit(1)
