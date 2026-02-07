


import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, FastLED_Types


port = '/dev/ttyACM0'  # Adjust as necessary for your system
baud = 115200
delay = 1  # seconds


config = USBTransportConfig(port=port, baud=baud, debug=True)
gpio_lib = GPIO_Lib(transport_config=config, require_ack_on_send=True)
# gpio_lib.setHandshakeEnabled(False)
gpio_lib.start()


gpio_lib.pinMode(
    38,
    "OUTPUT",
    "Backlight LCD"
)

gpio_lib.digital_write("Backlight LCD", False)  # Turn off backlight
time.sleep(delay)
gpio_lib.digital_write("Backlight LCD", True)  # Turn on backlight


fast_led = gpio_lib.FastLED(
    gpio_lib=gpio_lib,
    data_pin=40,
    clock_pin=39,
    led_count=1,
    led_type=FastLED_Types.APA102,
)


fast_led.setup()


fast_led.send_led_data(
    [(255, 0, 0)]
)  # Show red color

time.sleep(delay)

fast_led.send_led_data(
    [(0, 255, 0)]
)  # Show green color

time.sleep(delay)

fast_led.send_led_data(
    [(0, 0, 255)]
)  # Show blue color

time.sleep(delay)

fast_led.send_led_data(
    [(255, 255, 255)]
)  # Show white color

time.sleep(delay)

fast_led.send_led_data(
    [(0, 0, 0)]
)  # Turn off LEDs



delay_transition = 0.02  # seconds
steps_between_colors = -25


for i in range(2):
    # Smoothly transition from red to green to blue every cycle
    for r in range(255, -1, steps_between_colors):
        g = 255 - r
        fast_led.send_led_data([(r, g, 0)])
        time.sleep(delay_transition)
    for g in range(255, -1, steps_between_colors):
        b = 255 - g
        fast_led.send_led_data([(0, g, b)])
        time.sleep(delay_transition)
    for b in range(255, -1, steps_between_colors):
        r = 255 - b
        fast_led.send_led_data([(r, 0, b)])
        time.sleep(delay_transition)
fast_led.send_led_data(
    [(0, 0, 0)]
)  # Turn off LEDs




gpio_lib.await_send_empty()
gpio_lib.stop()

exit()  



# Brightness test
fast_led.send_led_data([(255,255,255)])

for brightness in range(255, -1, steps_between_colors):
    fast_led.setBrightness(brightness)

for brightness in range(0, 256, steps_between_colors * -1):
    fast_led.setBrightness(brightness)

