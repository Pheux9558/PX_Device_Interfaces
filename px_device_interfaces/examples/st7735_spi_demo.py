import random
import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib


# T-Dongle S3 ST7735 wiring
# SCK  -> GPIO5
# MOSI -> GPIO3
# CS   -> GPIO4
# RS   -> GPIO2
# RST  -> GPIO1
# LEDA -> GPIO38 (active low)

random_str_list = [
    "Hello, World!",
    "The quick brown fox jumps over the lazy dog.",
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "Python is a great programming language.",
    "Testing 12345",
    "GPIO_Lib Display Demo",
    "ST7735 SPI Interface",
    "This is a random string.",
    "Another random string for testing.",
    "The rain in Spain stays mainly in the plain.",
    "Sphinx of black quartz, judge my vow.",
    "Pack my box with five dozen liquor jugs.",
    "How vexingly quick daft zebras jump!",
    "Bright vixens jump; dozy fowl quack.",
    "Quick zephyrs blow, vexing daft Jim.",
    "Two driven jocks help fax my big quiz.",
    "The five boxing wizards jump quickly.",
    "Jackdaws love my big sphinx of quartz.",
    "The lazy dog is sleeping.",
    "A quick movement of the enemy will jeopardize six gunboats.",
    "All questions asked by five watched experts amaze the judge.",
    "The jay, pig, fox, zebra, and my wolves quack!",
]


def main() -> None:
    config = USBTransportConfig(port="/dev/ttyACM0", baud=115200, debug=True)
    gpio = GPIO_Lib(transport_config=config, require_ack_on_send=True, send_ack_timeout=.2)

    gpio.start()
    gpio.setDebugEnabled(False)

    if not gpio._transport:
        raise RuntimeError("Failed to initialize transport")
    gpio._transport.resetDevice()
    time.sleep(1)  # wait for device to reset

    gpio.setDebugEnabled(True)


    spi = GPIO_Lib.SPI(gpio_lib=gpio, data_pin=3, clock_pin=5, frequency=40_000_000)
    lcd = GPIO_Lib.Display(
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

    lcd.set_backlight(True)
    lcd.set_rotation(3)
    lcd.clear()
    lcd.write_text("Hello, World!", x=5, y=5)
    lcd.set_rotation(1)
    lcd.write_text("Hello, World!", x=5, y=5)



    for pos in range(5):
        lcd.write_text(random.choice(random_str_list), x=5, y=10 + pos * 10)

    gpio.await_send_empty()

    # Example bitmap: 20x20 red square in RGB565 little-endian
    w = 20
    h = 20
    red = 0xF800
    bitmap = bytearray()
    for _ in range(w * h):
        bitmap.extend(red.to_bytes(2, "little"))
    lcd.write_bitmap(bitmap, x_pos=0, y_pos=20, x_len=w, y_len=h)

    gpio.await_send_empty()
    gpio.stop()


if __name__ == "__main__":
    main()
