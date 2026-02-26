
import time

from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib




def main() -> None:
    cfg = USBTransportConfig(port="/dev/ttyACM0", baud=921600, debug=True, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)

    try:
        gpio.start()

        lcd = GPIO_Lib.Display.DisplayHD44780(
            gpio_lib=gpio,
            i2c=GPIO_Lib.I2C(gpio_lib=gpio, i2c_bus=0),
            address=0x27,
            cols=16,
            rows=2,
        )
        lcd.clear()
        lcd.set_cursor(0, 0)
        lcd.write_text("Hello, World!")
        lcd.set_cursor(0, 1)
        lcd.write_text("HD44780 OK")
        time.sleep(2)
        lcd.set_backlight(False)
        time.sleep(1)
        lcd.set_backlight(True)
        time.sleep(1)











    except Exception as e:
        print(f"Error during GPIO_Lib operation: {e}")
        raise
    finally:
        gpio.stop()








if __name__ == "__main__":
    main()