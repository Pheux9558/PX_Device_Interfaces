

# test fireware response of PX devices
import serial
import serial.tools.list_ports
import pytest
import struct
import time
from pathlib import Path
import sys

def send_command(ser: serial.Serial, cmd: int, payload: bytes = b''):
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

    ser.write(packet)
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

    print(f"Received response cmd=0x{resp_cmd:04X}, len={resp_len}")
    return resp_cmd, resp_payload

def test_firmware_response():
    # Auto-discover a suitable serial port for testing (prefer /dev/ttyACM*).
    ports = serial.tools.list_ports.comports()
    if not ports:
        pytest.skip("No serial ports available to test firmware response")
    acm_ports = [p.device for p in ports if 'ACM' in p.device]
    port = acm_ports[0] if acm_ports else ports[0].device

    with serial.Serial(port, 115200, timeout=1) as ser:
        # Test firmware info command
        time.sleep(2)  # wait for device to be ready

        resp_cmd, resp_payload = send_command(ser, 0xFFFE)
        if resp_cmd != 0xFFFE:
            print(f"Unexpected response command: {resp_cmd}")
        else:
            raw = resp_payload.decode('utf-8', errors='replace')
            firmware_name = raw.strip('\x00').strip()
            prefix = 'GPIO_Lib_Firmware_'
            if firmware_name.startswith(prefix):
                device_name = firmware_name[len(prefix):]
                print(f"Firmware Name: {firmware_name} (device: {device_name})")
            else:
                print(f"Firmware Name: {firmware_name}")

        # Test firmware version command
        resp_cmd, resp_payload = send_command(ser, 0xFFFF)
        if resp_cmd != 0xFFFF or len(resp_payload) != 3:
            print(f"Unexpected response for version: {resp_cmd}, payload length: {len(resp_payload)}")
        else:
            major, minor, patch = struct.unpack('<BBB', resp_payload)
            print(f"Firmware Version: {major}.{minor}.{patch}")

if __name__ == "__main__":
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
    # only test /dev/ttyAC* ports
    acm_ports = [p for p in ports if 'ACM' in p.device]
    if acm_ports:
        for port in acm_ports:
            print(f"Testing port: {port.device}")
            try:
                test_firmware_response()
            except Exception as e:
                print(f"Error testing port {port.device}: {e}") 
    else:
        for port in ports:
            print(f"Testing port: {port.device}")
            try:
                test_firmware_response()
            except Exception as e:
                print(f"Error testing port {port.device}: {e}")