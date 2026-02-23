
import time

from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode

def test_firmware_info():
    cfg = USBTransportConfig(port="/dev/ttyACM0", baud=921600, debug=False, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)
    gpio.setHandshakeEnabled(True)
    try:
        gpio.start()
        time.sleep(0.5)
        gpio.requestFirmwareInfo()

        print(f"Firmware Name: {gpio.firmware_name}")
        print(f"Firmware Version: {gpio.firmware_version}")
        print(f"Firmware Build Flags: {gpio.firmware_build_flags}")
    finally:
        gpio.stop()

test_firmware_info()