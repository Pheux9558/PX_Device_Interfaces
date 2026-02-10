

# WIP





# Cleaner version of scan_or_select.py

# Try to find known devices on known ports and test firmware response.
# If found, set up compile configuration accordingly.
# User musst confirm the device or select from a list if multiple found.
# If device dont have a valid response, user must select device config manually.
# Build flags can be edited in the cli before proceeding.
# This script is intended to be imported and used by pio_pre_hook.py.



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

# Build flags to add for device configuration
build_flag_list = [
    '-DDEBUG',                 # Enable debug output
    '-DI2C_SUPPORT',           # Enable I2C
    '-DSPI_SUPPORT',           # Enable SPI
    '-DUART_SUPPORT',          # Enable UART
    '-DWiFi_SUPPORT',          # Enable WiFi
    '-DBLUETOOTH_SUPPORT',     # Enable Bluetooth
    '-DLCD_SUPPORT',           # Enable LCD
    '-DSD_CARD_SUPPORT',       # Enable SD Card
    '-DOLED_SUPPORT',          # Enable OLED
    '-DIPS_SUPPORT',   # Enable IPS Display
    '-DTOUCHSCREEN_SUPPORT',   # Enable Touchscreen
]

def print_seperator():
    print("=" * 40)









def list_ports() -> list[dict]:
    """List available serial ports if description is available."""
    ports = list(serial.tools.list_ports.comports())
    out = []
    for p in ports:
        if p.description and p.description.lower() != "n/a":
            out.append({'device': p.device, 'desc': p.description or '', 'hwid': p.hwid or ''})
    return out





# region Device communication functions
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



# region Firmware info retrieval
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


# region Build flag editing functions
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




# region DeviceCompileConfig class
class DeviceCompileConfig:
    """Holds device-specific compile configuration."""
    def __init__(self, build_flags: list, upload_speed: int, framework: str):
        self.build_flags = build_flags
        self.upload_speed = upload_speed
        self.framework = framework

    def __str__(self):
        return f'DeviceCompileConfig(build_flags={self.build_flags}, upload_speed={self.upload_speed}, framework={self.framework})'
    
    def setBuildFlags(self, flags: list):
        self.build_flags = flags

    def setUploadSpeed(self, speed: int):
        self.upload_speed = speed

    def setFramework(self, framework: str):
        self.framework = framework    
    