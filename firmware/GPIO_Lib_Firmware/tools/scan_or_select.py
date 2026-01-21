# Try to find known devices on known ports and test firmware response
# If found, update platformio.ini with the detected env and upload_port.
# Get Build Flags from detected device for PlatformIO configuration with byte 0xFFFD.
# If multiple devices found, select by user input.
# If no devices found, scan all ports, print results and let user select or abort if no selection.
# write platformio.ini with detected env, build flags and upload_port.

import sys
import serial
import serial.tools.list_ports
import struct
import time
import os



CMD_FIRMWARE_BUILD_FLAGS = 0xFFFD           # Response with build flags, returns: (build flags string in UTF-8)
CMD_FIRMWARE_INFO = 0xFFFE                  # Response with firmware info, returns (name string in UTF-8) # Name of the device configuration
CMD_FIRMWARE_VERSION = 0xFFFF               # Response with firmware version, returns: (major, minor, patch)



ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INI_PATH = os.path.join(ROOT, 'platformio.ini')


known_ports = [
    '/dev/ttyACM0',
    '/dev/ttyACM1',
    '/dev/ttyUSB0',
    '/dev/ttyUSB1',
    'COM3',
    'COM4',
]

# Non-interactive flag: when present, scanner should not prompt the user
# and should auto-select sensible defaults (used by PlatformIO extra-scripts)
AUTO_YES = "--yes" in sys.argv
# Build flags to add for device configuration
build_flag_list = [
    '-DDEBUG',          # Enable debug output
    '-DGPIO',           # Enable GPIO
    '-DI2C',            # Enable I2C
    '-DSPI',            # Enable SPI
    '-DUART',           # Enable UART
    '-DWiFi',           # Enable WiFi
    '-DBLUETOOTH',      # Enable Bluetooth
    '-DLCD',            # Enable LCD
    '-DSD_CARD',        # Enable SD Card
    '-DOLED',           # Enable OLED
    '-DIPS_DISPLAY',    # Enable IPS Display
    '-DTOUCHSCREEN',    # Enable Touchscreen
    '-DESP32_PICO_D4'   # Enable ESP32 Pico D4 specific features
]

def print_seperator():
    print("=" * 40)


def determine_device_metadata(firmware_info: str) -> dict:
    """Derive PlatformIO environment metadata from firmware_info string."""
    info = (firmware_info or '').lower()
    # print info for debugging
    if 'uno' in info or 'arduino' in info:
        return {
            'env': 'uno',
            'platform': 'atmelavr',
            'board': 'uno',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            'default_build_flags': '-DARDUINO_UNO -Ilib'
        }
    if 'esp32' in info:
        return {
            'env': 'esp32',
            'platform': 'espressif32',
            'board': 'esp32dev',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '921600',
            # ESP32 is FreeRTOS-capable; default flags enable RTOS usage in firmware
            'default_build_flags': '-DESP32_PICO_D4 -Ilib -DLARGE_BUFFERS'
        }
    if 'stm32' in info:
        return {
            'env': 'stm32',
            'platform': 'ststm32',
            'board': 'genericSTM32F103C',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            # STM32 is FreeRTOS-capable; enable RTOS by default
            'default_build_flags': '-DARDUINO_STM32 -Ilib -DLARGE_BUFFERS'
        }
    if 'rp2040' in info or 'pico' in info or 'raspberry' in info:
        return {
            'env': 'rp2040',
            'platform': 'raspberrypi',
            'board': 'raspberry-pi-pico',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            # RP2040 commonly runs with FreeRTOS or can support it; enable by default
            'default_build_flags': '-DRP2040 -Ilib'
        }
    if 'nrf' in info or 'nrf52' in info or 'nordic' in info:
        return {
            'env': 'nrf52',
            'platform': 'nordicnrf52',
            'board': 'pca10040',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            'default_build_flags': '-DNORDIC_NRF52 -Ilib'
        }
    if 'samd' in info or 'zero' in info or 'samd21' in info:
        return {
            'env': 'samd',
            'platform': 'atmelsam',
            'board': 'arduino_zero',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            # SAMD (Cortex-M) can run FreeRTOS; enable by default
            'default_build_flags': '-DSAMD21 -Ilib'
        }
    if 'mega' in info or 'megaavr' in info or 'atmega' in info:
        return {
            'env': 'megaavr',
            'platform': 'atmelavr',
            'board': 'megaatmega2560',
            'framework': 'arduino',
            'monitor_speed': '115200',
            'upload_speed': '',
            'default_build_flags': '-DARDUINO_MEGAAVR -Ilib'
        }
    # fallback
    return {
        'env': 'esp32',
        'platform': 'espressif32',
        'board': 'esp32dev',
        'framework': 'arduino',
        'monitor_speed': '115200',
        'upload_speed': '921600',
        'default_build_flags': '-Ilib'
    }


def map_board_mcu_to_metadata(board_token: str | None, mcu_token: str | None) -> dict:
    """Map BOARD and MCU tokens to platformio metadata.
    board_token, mcu_token: strings like 'esp32', 'rp2040', 'arduino_uno', 'stm32'
    Returns same dict shape as determine_device_metadata()
    """
    b = (board_token or '').lower()
    m = (mcu_token or '').lower()
    if 'uno' in b or 'arduino_uno' in b or 'atmega328p' in m:
        return {
            'env': 'uno', 'platform': 'atmelavr', 'board': 'uno', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-DARDUINO_UNO -Ilib'
        }
    if 'esp32' in b or 'esp32' in m:
        # prefer specific MCU
        default = '-DESP32_PICO_D4 -Ilib' if 'pico' in m or 'pico_d4' in m else '-Ilib'
        return {
            'env': 'esp32', 'platform': 'espressif32', 'board': 'esp32dev', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '921600', 'default_build_flags': default
        }
    if 'esp8266' in b or 'esp8266' in m:
        return {
            'env': 'esp8266', 'platform': 'espressif8266', 'board': 'esp12e', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-Ilib'
        }
    if 'rp2040' in b or 'rp2040' in m or 'pico' in b:
        return {
            'env': 'rp2040', 'platform': 'raspberrypi', 'board': 'raspberry-pi-pico', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-DRP2040 -Ilib'
        }
    if 'nrf' in b or 'nrf' in m:
        return {
            'env': 'nrf52', 'platform': 'nordicnrf52', 'board': 'pca10040', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-DNORDIC_NRF52 -Ilib'
        }
    if 'samd' in b or 'samd' in m:
        return {
            'env': 'samd', 'platform': 'atmelsam', 'board': 'arduino_zero', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-DSAMD21 -Ilib'
        }
    if 'stm32' in b or 'stm32' in m:
        return {
            'env': 'stm32', 'platform': 'ststm32', 'board': 'genericSTM32F103C', 'framework': 'arduino',
            'monitor_speed': '115200', 'upload_speed': '', 'default_build_flags': '-DARDUINO_STM32 -Ilib'
        }
    # fallback
    return {
        'env': 'esp32', 'platform': 'espressif32', 'board': 'esp32dev', 'framework': 'arduino',
        'monitor_speed': '115200', 'upload_speed': '921600', 'default_build_flags': '-Ilib'
    }


def ask(prompt: str) -> str:
    """Write prompt to stdout and flush, then read a line from stdin.

    Using this avoids missing prompts when stdout is buffered or redirected
    (common in IDEs / PlatformIO extra-script execution).
    """
    sys.stdout.write(prompt + "\n")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        return ''
    return line.rstrip('\n')


def send_command(ser: serial.Serial, cmd: int, payload: bytes = b'') -> tuple[int, bytes]:
    """Send a framed command and read a framed response using the
    GPIO_Lib framing: [0xAA][CMD(2)][LEN(2)][PAYLOAD...][CHK]

    CHK = (CMD + LEN + sum(PAYLOAD)) & 0xFF
    """
    # build packet
    start = bytes([0xAA])
    cmd_bytes = int(cmd).to_bytes(2, "little")
    len_bytes = int(len(payload)).to_bytes(2, "little")
    chk = (cmd + len(payload) + sum(payload)) & 0xFF
    packet = start + cmd_bytes + len_bytes + payload + bytes([chk])

    # send packet
    ser.write(packet)
    # Ensure all data is sent before reading response
    ser.flush()

    # read until start byte
    deadline = time.time() + ser.timeout if ser.timeout else None
    while True:
        b = ser.read(1)
        if not b:
            raise RuntimeError("No response from device (timeout waiting for start byte)")
        if b[0] == 0xAA:
            break
        # keep reading until we see start byte

    header = ser.read(4)
    if len(header) < 4:
        raise RuntimeError("Incomplete header from device")
    resp_cmd, resp_len = struct.unpack('<HH', header)

    # sanity limit for payload length to avoid allocating huge buffers
    MAX_PAYLOAD = 64 * 1024
    if resp_len > MAX_PAYLOAD:
        raise RuntimeError(f"Unreasonable payload length from device: {resp_len}")

    resp_payload = b''
    remaining = resp_len
    while remaining > 0:
        chunk = ser.read(remaining)
        if not chunk:
            raise RuntimeError("Incomplete response from device (payload timeout)")
        resp_payload += chunk
        remaining -= len(chunk)

    chk_b = ser.read(1)
    if len(chk_b) < 1:
        raise RuntimeError("Missing checksum byte from device")
    resp_chk = chk_b[0]

    # verify checksum
    if ((resp_cmd + resp_len + sum(resp_payload)) & 0xFF) != resp_chk:
        raise RuntimeError("Checksum mismatch on response")

    # print(f"Received response cmd=0x{resp_cmd:04X}, len={resp_len}")
    return resp_cmd, resp_payload

def get_firmware(ser: serial.Serial):
    """Get firmware Version, info and build flags from device."""

    resp_cmd_version, payload_version = send_command(ser, CMD_FIRMWARE_VERSION)
    if resp_cmd_version != CMD_FIRMWARE_VERSION:
        raise RuntimeError(f"Unexpected response command: 0x{resp_cmd_version:04X}")
    if len(payload_version) != 3:
        raise RuntimeError(f"Unexpected payload length for version: {len(payload_version)}")
    major, minor, patch = struct.unpack('<BBB', payload_version)
    firmware_version = (major, minor, patch)

    resp_cmd_info, payload_info = send_command(ser, CMD_FIRMWARE_INFO)
    if resp_cmd_info != CMD_FIRMWARE_INFO:
        raise RuntimeError(f"Unexpected response command: 0x{resp_cmd_info:04X}")
    firmware_info = payload_info.decode('utf-8', errors='replace')

    resp_cmd_build_flags, payload_build_flags = send_command(ser, CMD_FIRMWARE_BUILD_FLAGS)
    if resp_cmd_build_flags != CMD_FIRMWARE_BUILD_FLAGS:
        raise RuntimeError(f"Unexpected response command: 0x{resp_cmd_build_flags:04X}")
    build_flags = payload_build_flags.decode('utf-8', errors='replace')

    # print debug info
    print(f"Firmware Version: {firmware_version}, Info: '{firmware_info}', Build Flags: '{build_flags}'")
    
    return firmware_version, firmware_info, build_flags


def scan_known_ports(known_ports) -> list[dict]:
    """Scan known ports for connected devices.

    known_ports: list of ports to scan
    returns: list of tuples (port dict, detected type str)
    """
    detected = []
    for p in known_ports:
        try:
            print(f"Try to connect to port [{p}] -> ", end="")
            with serial.Serial(p, 115200, timeout=1) as ser:
                # give some time for device to reset if needed
                time.sleep(2)
                firmware_version, firmware_info, build_flags = get_firmware(ser)
                # add -D infront of each build flag if not present
                build_flags = ' '.join([f if f.startswith('-D') else f'-D{f}' for f in build_flags.split()])
                print("[OK]")
                # print(f"Detected device on {p}: version={firmware_version}, info='{firmware_info}'")
                meta = determine_device_metadata(firmware_info)
                detected.append({
                    'port': p,
                    'firmware_version': firmware_version,
                    'firmware_info': firmware_info,
                    'build_flags': build_flags,
                    # include inferred metadata for update_ini
                    'env': meta['env'],
                    'platform': meta['platform'],
                    'board': meta['board'],
                    'framework': meta['framework'],
                    'monitor_speed': meta['monitor_speed'],
                    'upload_speed': meta['upload_speed'],
                    'default_build_flags': meta['default_build_flags']
                })
        except Exception as e:
            if "No response from device" in str(e):
                print("[No response]")
            elif "could not open port" in str(e).lower():
                print("[Port not found]")
            else:
                print(f"[FAIL] ({e})")
    return detected


def list_ports() -> list[dict]:
    """List available serial ports if description is available."""
    ports = list(serial.tools.list_ports.comports())
    out = []
    for p in ports:
        if p.description and p.description.lower() != "n/a":
            out.append({'device': p.device, 'desc': p.description or '', 'hwid': p.hwid or ''})
    return out

def configuer_device(port) -> dict | None:
    """
    Configure new device on given port.
    User can configure:
    - device type (uno, esp32, stm32)
    - firmware info
    - build flags
    Returns device dict with keys 'port', 'firmware_info', 'build_flags' or None if aborted.
    """
    print(f"Now entering device configuration mode for port {port}.")
    # select device type
    print("Select device type:")
    print("  [0] Arduino Uno")
    print("  [1] ESP32")
    print("  [2] STM32")
    s = ask('Select device type by number or press Enter to abort> ').strip()
    if s == '':
        print("Aborting.")
        return None
    
    # set firmware info
    # "GPIO_Lib_Firmware_<device type>_<custom name>"
    # default custom name is empty without trailing underscore
    device_type = None

    if s == '0':
        device_type = 'uno'
    elif s == '1':
        device_type = 'esp32'
    elif s == '2':
        device_type = 'stm32'
    else:
        print("Invalid selection, aborting.")
        return None
    print("Setup firmware info for device.")
    custom_name = ask('Enter custom name for device (or press Enter for none)> ').strip()
    if custom_name:
        firmware_info = f"GPIO_Lib_Firmware_{device_type}_{custom_name}"
    else:
        firmware_info = f"GPIO_Lib_Firmware_{device_type}"
    print(f"Configured device firmware info: {firmware_info}")

    # set build flags (allow interactive editing)
    build_flags = edit_build_flags('')
    meta = determine_device_metadata(firmware_info)
    return {
        'port': port,
        'firmware_info': firmware_info,
        'build_flags': f"-DDEVICE_TYPE_{device_type.upper()} {build_flags}",
        'env': meta['env'],
        'platform': meta['platform'],
        'board': meta['board'],
        'framework': meta['framework'],
        'monitor_speed': meta['monitor_speed'],
        'upload_speed': meta['upload_speed'],
        'default_build_flags': meta['default_build_flags']
    }

    

def update_ini(device) -> bool:
    """Update platformio.ini with detected device info.

    device: dict with keys 'port', 'firmware_info', 'build_flags'
    """
    if AUTO_YES:
        # touch ini to ensure it updates timestamp
        with open(INI_PATH, 'a'):
            pass
        print("AUTO_YES mode: touched platformio.ini without changes.")
        return True
    
    # Ensure device has essential fields, derive metadata when absent
    if not device:
        print('No device information provided to update_ini()')
        return False
    meta = determine_device_metadata(device.get('firmware_info', ''))
    target_env = device.get('env') or meta['env']

    # Compute build flags: merge device build_flags and default if needed
    device_flags = (device.get('build_flags') or '').strip()
    default_flags = meta.get('default_build_flags', '').strip()
    # merge preserving order and avoiding duplicates
    def merge_flags(a: str, b: str) -> str:
        parts = []
        for token in (a + ' ' + b).split():
            if token not in parts:
                parts.append(token)
        return ' '.join(parts)

    final_build_flags = merge_flags(device_flags, default_flags)

    # sanitize build flags for writing into platformio.ini
    # replace common separators and unsafe characters used previously
    if final_build_flags:
        # replace semicolons with spaces and convert colon-based kv to equals
        final_build_flags = final_build_flags.replace(';', ' ')
        final_build_flags = final_build_flags.replace(':', '=')
        # collapse multiple whitespace
        final_build_flags = ' '.join(final_build_flags.split())
        # escape double-quotes so the value can be wrapped safely
        final_build_flags = final_build_flags.replace('"', '\\"')

    # Attempt to derive metadata from BOARD= / MCU= tokens in build flags
    board_token = None
    mcu_token = None
    if final_build_flags:
        for tok in final_build_flags.split():
            if tok.upper().startswith('BOARD='):
                board_token = tok.split('=', 1)[1]
            if tok.upper().startswith('MCU='):
                mcu_token = tok.split('=', 1)[1]

    if board_token or mcu_token:
        meta = map_board_mcu_to_metadata(board_token, mcu_token)

    # Compose minimal platformio.ini with a single env
    lines = []
    lines.append('; Generated by scan_or_select.py')
    lines.append('[platformio]')
    lines.append(f'default_envs = {target_env}')
    lines.append('')
    # Do NOT enable interactive pre/post hooks by default; keep them commented
    lines.append('[env]')
    lines.append('extra_scripts = pre:tools/pio_pre_hook.py, post:tools/pio_post_hook.py')
    lines.append('')
    lines.append(f'[env:{target_env}]')
    lines.append(f'platform = {device.get("platform") or meta["platform"]}')
    lines.append(f'board = {device.get("board") or meta["board"]}')
    lines.append(f'framework = {device.get("framework") or meta["framework"]}')
    lines.append('lib_extra_dirs = lib')
    lines.append(f'upload_port = {device.get("port").replace("\\\n","") if device.get("port") else ""}')
    if device.get('upload_speed'):
        lines.append(f'upload_speed = {device.get("upload_speed")}')
    elif meta.get('upload_speed'):
        if meta.get('upload_speed'):
            lines.append(f'upload_speed = {meta.get("upload_speed")}')
    if device.get('monitor_speed') or meta.get('monitor_speed'):
        lines.append(f'monitor_speed = {device.get("monitor_speed") or meta.get("monitor_speed")}')
    if final_build_flags:
        # further sanitize: allow only alnum and a small set of punctuation
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_=./+ ")
        cleaned = []
        for ch in final_build_flags:
            if ch in allowed:
                cleaned.append(ch)
            else:
                # replace unsafe char with underscore to keep token separation
                cleaned.append('_')
        final_build_flags = ' '.join(''.join(cleaned).split())
        # wrap in quotes so spaces are preserved and the value is a single token
        lines.append(f'build_flags = {final_build_flags}')
    # final write
    try:
        with open(INI_PATH, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        print(f'Wrote {INI_PATH} with env {target_env}')
        return True
    except Exception as e:
        print('Failed to write platformio.ini:', e)
        return False

def edit_build_flags(original_flags: str) -> str:
    """Allow user to edit build flags interactively with toggle behavior."""
    print("Current build flags:")
    print(original_flags)
    # parse original into a set of flags
    initial = set(original_flags.split()) if original_flags and original_flags.strip() else set()
    selected = set(initial)

    while True:
        print("\nAvailable build flags (selected flags marked with [X]):")
        for i, flag in enumerate(build_flag_list):
            mark = "X" if flag in selected else " "
            print(f"  [{i}] [{mark}] {flag}")
        s = ask("Toggle flags by number separated by spaces, 'a' to toggle all, 'c' to clear all, Enter to finish> ").strip()
        if s == "":
            break
        if s.lower() == "c":
            selected.clear()
            continue
        if s.lower() == "a":
            # if all selected, clear; otherwise select all
            if all(f in selected for f in build_flag_list):
                selected.clear()
            else:
                selected.update(build_flag_list)
            continue
        parts = s.split()
        for part in parts:
            try:
                idx = int(part)
                if idx < 0 or idx >= len(build_flag_list):
                    raise ValueError()
                flag = build_flag_list[idx]
                if flag in selected:
                    selected.remove(flag)
                else:
                    selected.add(flag)
            except Exception:
                print(f"Ignoring invalid selection '{part}'")

    # preserve canonical order from build_flag_list
    final_flags = " ".join([f for f in build_flag_list if f in selected])
    print("Final build flags:")
    print(final_flags)
    return final_flags



def main_program_run() -> dict | None:
    """Scan serial ports for known devices and test firmware response.
    If found, update platformio.ini with detected env, upload_port and build_flags.
    If multiple devices found, select by user input.
    If no devices found, scan all ports, print results and let user select or abort if no selection.
    """
    print("Scanning known ports for devices...")
    print_seperator()
    # If running non-interactively (PlatformIO extra-scripts), do a quick
    # scan and auto-select the first detected device instead of prompting.
    if AUTO_YES:
        print("Running in non-interactive --yes mode: scanning known ports...")
        detected = scan_known_ports(known_ports)
        print_seperator()
        if detected:
            print(f"Auto-selected device on port {detected[0]['port']}")
            # return the first detected device for automated workflows
            return detected[0]
        print("No devices found in --yes mode; skipping interactive selection.")
        return None
    print_seperator()
    detected = scan_known_ports(known_ports)
    if detected:
        if len(detected) > 1:
            print("Multiple devices detected:")
            for i, d in enumerate(detected):
                print(f"  [{i}] Port: {d['port']}, Info: {d['firmware_info']}, Version: {d['firmware_version']}, Build Flags: {d['build_flags']}")
            s = ask('Select device by number> ').strip()
            try:
                idx = int(s)
                if idx < 0 or idx >= len(detected):
                    raise ValueError()
                detected = detected[idx]
            except Exception:
                print('Invalid selection, aborting.')
                detected = None
        else:
            detected = detected[0]
        if detected:
            
            # confirm by user if the selected device is correct
            if not confirm_by_user(detected):
                print("Aborting.")
                sys.exit(1)
                return None
            
            # Ask user to edit build flags or accept detected
            print("Do you want to edit the detected build flags?")
            s = ask('Edit build flags? (y/N)> ').strip().lower()
            if s == 'y' or s == 'yes':
                new_flags = edit_build_flags(detected['build_flags'])
                detected['build_flags'] = new_flags
            return detected
    else:
        print("No known devices detected on known ports.")
        print("Scanning all available serial ports...\n")
        ports = list_ports()
        if not ports:
            print("No serial ports found.")
            return None
        print("Available serial ports:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p['device']} - {p['desc']} ({p['hwid']})")
        print("If your device is listed above, you can configure it now.")    
        s = ask('Select device by number or press Enter to abort> ').strip()
        if s == '':
            print("Aborting.")
            sys.exit(1)
            return None
        device = configuer_device(ports[int(s)]['device'])
        if device:
            if confirm_by_user(device):
                return device
            else:
                print("Aborting.")
                sys.exit(1)
                return None
    return None
  
        

def confirm_by_user(device) -> bool:
    """Confirm device selection by user."""
    print("\n" * 2)
    print_seperator()
    print("Device selected successfully.")
    print(f"Selected device on port {device['port']}")
    print(f"Firmware Info: {device['firmware_info']}")
    print(f"Build Flags: {device['build_flags']}")
    print_seperator()
    s = ask('Use this device? (Y/n)> ').strip().lower()
    if s == '' or s == 'y' or s == 'yes':
        return True
    return False


def scan_or_select_and_write_ini() -> dict | None:
    """Main entry point to scan or select device and write platformio.ini."""
    device = main_program_run()
    print_seperator()
    print("Updating platformio.ini...")
    if device:
        if update_ini(device):
            print("platformio.ini updated successfully.")
        else:
            print("Failed to update platformio.ini.")
        return device


if __name__ == "__main__":
    device = scan_or_select_and_write_ini()
    print("\n\n\nResult:", device)