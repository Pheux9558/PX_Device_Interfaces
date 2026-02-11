"""Show an RGB565 binary file on an ST7735 display (example)

Reads a binary file containing little-endian RGB565 pixel data and sends it
to the display using the `Display.write_bitmap()` API.

Usage:
    python -m px_device_interfaces.examples.show_rgb565_file --file rgb565data.bin --width 160 --height 80 --port /dev/ttyACM0
    python -m px_device_interfaces.examples.show_rgb565_file --file rgb565data.bin --width 160 --height 80 --port /dev/ttyACM0 --x 40
Defaults assume an ST7735 wired like `st7735_spi_demo.py` and a device on
`/dev/ttyACM0` using 921600 baud.


source /home/pheux/Documents/projects/0_python/PX_Device_Interfaces/.venv/bin/activate 2>/dev/null || true && python -m px_device_interfaces.examples.show_rgb565_file --file "px_device_interfaces/examples/rgb565data.bin" --width 80 --height 80 --port /dev/ttyACM0 --x 40 --random-rows

"""

from pathlib import Path
import argparse
import time
import sys

from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, PinMode


def parse_args():
    p = argparse.ArgumentParser(description="Display an RGB565 binary file on ST7735")
    p.add_argument("--file", "-f", default=str(Path(__file__).resolve().parent / "rgb565data.bin"), help="Path to RGB565 binary file (little-endian)")
    p.add_argument("--width", "-W", type=int, default=160, help="Bitmap width in pixels")
    p.add_argument("--height", "-H", type=int, default=80, help="Bitmap height in pixels")
    p.add_argument("--x", type=int, default=0, help="X position on display")
    p.add_argument("--y", type=int, default=0, help="Y position on display")
    p.add_argument("--port", default="/dev/ttyACM0", help="Serial port to use (default: /dev/ttyACM0)")
    p.add_argument("--baud", type=int, default=921600, help="Serial baud (default: 921600)")
    p.add_argument("--rotation", type=int, default=1, choices=[0,1,2,3], help="Display rotation")
    p.add_argument("--random-rows", dest="random_rows", action="store_true", help="Send rows in random order")
    p.add_argument("--no-backlight", dest="backlight", action="store_false", help="Don't enable backlight")
    p.set_defaults(backlight=True, random_rows=False)
    return p.parse_args()


def main():
    args = parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    data = file_path.read_bytes()
    expected = args.width * args.height * 2
    if len(data) != expected:
        print(f"File size ({len(data)} bytes) does not match expected size for {args.width}x{args.height} (expected {expected} bytes)")
        print("If your bitmap has different dimensions, re-run with --width and --height as appropriate.")
        sys.exit(2)

    # Setup transport and GPIO_Lib
    cfg = USBTransportConfig(port=args.port, baud=args.baud, debug=False)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)

    try:
        gpio.start()
        gpio.sync()
        time.sleep(0.5)

        # SPI / Display wiring (same as st7735_spi_demo)
        spi = GPIO_Lib.SPI(gpio_lib=gpio, data_pin=3, clock_pin=5, frequency=40_000_000)
        lcd = GPIO_Lib.Display(
            gpio_lib=gpio,
            spi=spi,
            cs_pin=4,
            rs_pin=2,
            enable_pin=1,
            backlight_pin=38,
            backlight_inverted=True,
            width=args.width,
            height=args.height,
        )

        if args.backlight:
            lcd.set_backlight(16)
        lcd.set_rotation(args.rotation)
        lcd.clear()
        
        gpio.await_send_empty()

        start_time = time.time()
        print(f"Writing {args.width}x{args.height} bitmap from {file_path} to display at ({args.x},{args.y})")
        lcd.write_bitmap(data, x_pos=args.x, y_pos=args.y, x_len=args.width, y_len=args.height, random_rows=args.random_rows)

        gpio.await_send_empty()
        total_time = time.time() - start_time
        print(f"Bitmap transfer complete in {total_time:.2f} seconds.\n"
              f"Transfer speed: {len(data)/1024/total_time:.2f} KB/s\n"
              f"Display should show the image now."
        )
        time.sleep(3)

    except Exception as e:
        print("Error during display operation:", e)
        raise
    finally:
        try:
            pass
            # lcd.set_backlight(False)
        except Exception:
            pass
        gpio.stop()


if __name__ == "__main__":
    main()
