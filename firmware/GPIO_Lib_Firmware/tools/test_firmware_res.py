

# firmware response utility for PX devices using GPIO_Lib API
import time
import sys
import serial.tools.list_ports
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib

def get_firmware_info(port: str, debug: bool = True) -> tuple[tuple[int, int, int], str, list[str]]:
    """Connect to a device on the given serial port and query firmware info.

    The low-level framing is handled by :class:`GPIO_Lib` and its
    :meth:`requestFirmwareInfo` helper.
    """
    cfg = USBTransportConfig(port=port, baud=921600, debug=False, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)
    gpio.setHandshakeEnabled(True)
    try:
        gpio.start()
        if not gpio.requestFirmwareInfo():
            print(f"Port {port}: failed to read firmware info")
        if debug:
            print(f"Port {port}: firmware name   = {gpio.firmware_name}")
            print(f"Port {port}: firmware version= {gpio.firmware_version}")
            print(f"Port {port}: build flags     = {gpio.firmware_build_flags}")
    finally:
        gpio.stop()
    return gpio.firmware_version, gpio.firmware_name, gpio.firmware_build_flags


if __name__ == "__main__":
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
        sys.exit(0)
    acm_ports = [p.device for p in ports if 'ACM' in p.device]
    target_ports = acm_ports if acm_ports else [p.device for p in ports]
    for port in target_ports:
        print(f"Testing port: {port}")
        try:
            get_firmware_info(port)
        except Exception as e:
            print(f"Error testing port {port}: {e}")
