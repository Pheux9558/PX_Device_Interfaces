

import signal
import sys
import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode



port = '/dev/ttyACM0'  # Adjust as necessary for your system
baud = 921600
config = USBTransportConfig(port=port, baud=baud, debug=True)
gpio_lib = GPIO_Lib(transport_config=config)

# Register cleanup handler for Ctrl+C and other signals
def cleanup_handler(signum, frame):
    print("\nInterrupted! Cleaning up...")
    gpio_lib.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)

gpio_lib.start()

led_count = 16 * 4  # Adjust based on your LED matrix size (e.g., 16x16 = 256 LEDs)

try:
    ws2812 = gpio_lib.FastLED.FastLEDWS2812(
        gpio_lib=gpio_lib,
        data_pin=12,
        led_count=led_count,
    )

    time.sleep(0.1)  # Short delay to ensure setup is complete before sending data
    ws2812.set_brightness(1)

    ws2812.send_led_data(
        [
            (255, 0, 0),  # Red
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 255, 255),  # White
            # fill the rest of the LEDs with off (0, 0, 0)
        ] + [(0, 0, 0)] * (ws2812.led_count - 7)  # Fill the rest of the LEDs with off (0, 0, 0)
    )



    delay = 1  # seconds
    time.sleep(delay)

    # set all leds to red, then green, then blue, with a delay in between
    ws2812.send_led_data(
        [(255, 0, 0)] * ws2812.led_count
    )  # Show red color
    time.sleep(delay)
    ws2812.send_led_data(
        [(0, 255, 0)] * ws2812.led_count
    )  # Show green color
    time.sleep(delay)
    ws2812.send_led_data(
        [(0, 0, 255)] * ws2812.led_count
    )  # Show blue color
    time.sleep(delay)

    # time.sleep(10)
    # delay = 0.1  # seconds
    # # repeat the below loop
    # for _ in range(5):
    #     # set one led to white, the rest off. the cycle leds one by one to white, then back to off
    #     for i in range(1, 7):
    #         led_data = [(255, 255, 255) if j == i else (0, 0, 0) for j in range(ws2812.led_count)]
    #         ws2812.send_led_data(led_data)
    #         time.sleep(delay)


    # turn off all leds at the end
    ws2812.send_led_data(
        [(0, 0, 0)] * ws2812.led_count
    )  # Turn off LEDs

finally:
    # Always cleanup, even if interrupted or exception occurs
    gpio_lib.stop()

