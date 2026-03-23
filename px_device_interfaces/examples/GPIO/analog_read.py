"""
This example demonstrates how to perform an analog read from pin A0 (pin 14) 
and optionally display the value on an SSD1306 OLED display. 
The example will run for 10 seconds, continuously reading the analog value
and printing it to the console. If the display is enabled, 
it will also show the current analog value.


Components needed:
- Arduino Uno R4 WiFi (or compatible board with GPIO_Lib firmware)
- Potentiometer connected to A0 (pin 14) with the following wiring:
  - One end to 5V
  - Other end to GND
  - Wiper (middle pin) to A0 (pin 14)
- Optional: SSD1306 OLED display connected via I2C (SDA to pin 20, SCL to pin 21, VCC to 3.3V, GND to GND)

Optional display code is included but can be disabled by setting `use_display = False`.
I2C port is configured for the QWIIC connector (i2c_bus=1) on the Uno R4, but can be adjusted as needed for different hardware setups.
Display is configured for a common SSD1306 128x64 OLED. 
Adjust I2C pins and display parameters as needed for your specific hardware.
(More details on display wiring and configuration can be found in the DisplaySSD1306 class documentation or examples.)
"""


import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode

use_display = True






def main() -> None:
    # Configure transport and GPIO_Lib
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