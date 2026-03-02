



import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode

use_display = True

def main() -> None:
    cfg = USBTransportConfig(port="/dev/ttyACM0", baud=921600, debug=False, reset_on_start=True)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)
    display = None
    if use_display:
        i2c = GPIO_Lib.I2C(gpio_lib=gpio, i2c_bus=1, frequency=400_000)
        display = GPIO_Lib.Display.DisplaySSD1306(
            gpio_lib=gpio,
            i2c=i2c,
            address=0x3C,
            width=128,
            height=64,
        )
    try:
        gpio.start()

        if use_display and display:
            display.set_rotation(0)
            display.clear()
            display.set_cursor(0, 0)
            display.write_text("Analog read A0:")

        # Configure pin 14 (A0) as analog input
        adc_pin = 14
        gpio.set_analog_read_resolution(14)
        gpio.pinMode(adc_pin, PinMode.ANALOG_INPUT)
        time.sleep(0.1)

        start_time = time.time()
        time_limit = 10  # seconds
        while time.time() - start_time < time_limit:
            value = gpio.analog_read(adc_pin)
            if use_display and display:                
                display.set_cursor(0, 10)
                # Use fixed-width format to overwrite previous value (14-bit ADC max: 16383)
                display.write_text(f"{value:>5}")

            print(f"Analog read from pin {adc_pin} (A0): {value}                    ", end="\r") 
            gpio.await_send_empty()

    except Exception as e:
        print(f"Error during GPIO_Lib operation: {e}")
        raise
    finally:
        gpio.stop()

if __name__ == "__main__":
    main()