


import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, FastLED_Types, PinMode


delay = .2  # seconds


delay_transition = 0.0  # seconds
steps_between_colors = -25



port = '/dev/ttyACM0'  # Adjust as necessary for your system
baud = 921600
config = USBTransportConfig(port=port, baud=baud, debug=True)
gpio_lib = GPIO_Lib(transport_config=config, require_ack_on_send=True, send_ack_timeout=.5)
gpio_lib.start()


gpio_lib.pinMode(
    38,
    PinMode.OUTPUT,
    "Backlight LCD"
)

gpio_lib.digital_write("Backlight LCD", False)  # Turn on backlight (active low)
time.sleep(delay)
gpio_lib.digital_write("Backlight LCD", True)  # Turn off backlight (active low)


fast_led = gpio_lib.FastLED(
    gpio_lib=gpio_lib,
    data_pin=40,
    clock_pin=39,
    led_count=1,
    led_type=FastLED_Types.APA102,
)


fast_led.setup()

if False:
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



if True:
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





if False:
    # Brightness test
    fast_led.send_led_data([(255,255,255)])

    for brightness in range(255, -1, steps_between_colors):
        fast_led.setBrightness(brightness)
        time.sleep(delay_transition)

    for brightness in range(0, 256, steps_between_colors * -1):
        fast_led.setBrightness(brightness)
        time.sleep(delay_transition)

    fast_led.send_led_data(
        [(0, 0, 0)]
    )  # Turn off LEDs




if True:
    # temp digital read test
    gpio_lib.pinMode(0, PinMode.INPUT, "Test Input")
    gpio_lib.sync()  # Ensure we're in sync with the device before starting the test
    # test btn stat for 5 seconds
    print("Testing digital read on pin 0 for 5 seconds. Press and release button if connected.")
    deadline = time.time() + 10
    while time.time() < deadline:
        val = gpio_lib.digital_read("Test Input")
        print(f"Pin 0 value: {val} \r", end="")
        time.sleep(0.1)

gpio_lib.await_send_empty()
gpio_lib.stop()
