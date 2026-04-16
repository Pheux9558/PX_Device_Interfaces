

"""
The dongle t3 has a single button connected to GPIO 0, which is also the BOOT button. 
This example demonstrates how to read the state of that button using the GPIO_Lib API and 
print a message to the Console and LCD when the button is pressed. The button is active low, 
so it will read as 0 when pressed and 1 when released.
Script runs for 10 seconds and updates button state every 0.5 seconds. 
Clears screen and prints final message before exiting.
"""

import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode

def main():
    cfg = USBTransportConfig(debug=False, reset_on_start=True, auto_connect=True)
    
    gpio = GPIO_Lib(transport_config=cfg, send_ack_timeout=1)
    spi = GPIO_Lib.SPI(gpio_lib=gpio, data_pin=3, clock_pin=5, frequency=40_000_000)
    lcd = GPIO_Lib.Display.DisplayST7735(
        gpio_lib=gpio,
        spi=spi,
        cs_pin=4,
        rs_pin=2,
        enable_pin=1,
        backlight_pin=38,
        backlight_inverted=True,
        width=80,
        height=160,
    )
    try:

        gpio.start()

        # Configure GPIO0 as input with pull-up resistor. This is the BOOT button on the dongle t3.
        gpio.pinMode(0, PinMode.INPUT_PULLUP, "BOOT")
        lcd.setup()
        lcd.set_rotation(1)
        lcd.set_backlight(16)

        gpio.await_send_empty()

        start_time = time.time()
        while time.time() - start_time < 10:  # Run for 10 seconds
            button_state = gpio.digital_read("BOOT")
            if button_state == 0:  # Button pressed (active low)
                # print("BOOT button pressed!")
                lcd.clear()
                lcd.write_text("BOOT button", x=5, y=5)
                lcd.write_text("pressed!", x=5, y=15)
                print("BOOT button pressed!")
                # print a small circle bitmap (RGB565) on the LCD to indicate button press
                # Green color in RGB565: 0x07E0
                circle_bitmap = [
                    0xFFFF, 0xFFFF, 0xFFFF, 0x07E0, 0x07E0, 0xFFFF, 0xFFFF, 0xFFFF,
                    0xFFFF, 0xFFFF, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0xFFFF, 0xFFFF,
                    0xFFFF, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0xFFFF,
                    0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0,
                    0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0,
                    0xFFFF, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0xFFFF,
                    0xFFFF, 0xFFFF, 0x07E0, 0x07E0, 0x07E0, 0x07E0, 0xFFFF, 0xFFFF,
                    0xFFFF, 0xFFFF, 0xFFFF, 0x07E0, 0x07E0, 0xFFFF, 0xFFFF, 0xFFFF,
                ]
                # API now handles RGB565 conversion automatically
                lcd.write_bitmap(circle_bitmap, x=60, y=50, width=8, height=8)
            else:
                 # print("BOOT button released")
                lcd.clear()
                lcd.write_text("BOOT button", x=5, y=5)
                lcd.write_text("released", x=5, y=15)
                print("BOOT button released")

            gpio.await_send_empty()
            time.sleep(0.5)  # Check button state every 0.5 seconds
        time.sleep(2)  # Show final message for 2 seconds before exiting

    finally:
        gpio.stop()

if __name__ == "__main__":
    main()
