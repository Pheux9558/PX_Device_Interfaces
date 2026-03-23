"""
Dual OLED test for Wire and Wire1 buses.
Tests I2C bus 0 (Wire) and bus 1 (Wire1) separately.
"""

import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib


def main() -> None:
    cfg = USBTransportConfig(port="/dev/ttyACM0", baud=921600, debug=False, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)

    try:
        gpio.start()
        gpio.sync()

        print("\n=== Testing Bus 0 (Wire) ===")
        i2c_0 = GPIO_Lib.I2C(gpio_lib=gpio, i2c_bus=0)
        print(f"Created I2C bus 0 with identifier {i2c_0.identifier}")

        display0 = GPIO_Lib.Display.DisplaySSD1306(
            gpio_lib=gpio,
            i2c=i2c_0,
            address=0x3C,
            width=128,
            height=64,
        )
        print(f"Created display 0 with identifier {display0.identifier}")

        print("Setting up display 0...")
        display0.setup()
        print("Display 0 setup complete")

        print("Clearing display 0...")
        display0.clear()
        print("Writing to display 0...")
        display0.set_cursor(0, 0)
        display0.write_text("Bus 0: Wire OK")
        print("Display 0 text written")
        time.sleep(2)

        print("\n=== Testing Bus 1 (Wire1) ===")
        i2c_1 = GPIO_Lib.I2C(gpio_lib=gpio, i2c_bus=1)
        print(f"Created I2C bus 1 with identifier {i2c_1.identifier}")

        display1 = GPIO_Lib.Display.DisplaySSD1306(
            gpio_lib=gpio,
            i2c=i2c_1,
            address=0x3C,
            width=128,
            height=32,
        )
        print(f"Created display 1 with identifier {display1.identifier}")

        print("Setting up display 1...")
        display1.setup()
        display1.set_rotation(2)
        print("Display 1 setup complete")

        print("Clearing display 1...")
        display1.clear()
        print("Writing to display 1...")
        display1.set_cursor(0, 0)
        display1.write_text("Bus 1: Wire1 OK")
        print("Display 1 text written")
        time.sleep(2)

        print("\n=== Testing alternating writes ===")
        for i in range(5):
            print(f"Write cycle {i+1}")
            display0.set_cursor(0, 10 * (i+1))
            display0.write_text(f"Bus 0 - {i+1}")
            display1.set_cursor(0, 10 * (i+1))
            display1.write_text(f"Bus 1 - {i+1}")
            # time.sleep(1)

        print("\nTest completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        gpio.stop()


if __name__ == "__main__":
    main()
