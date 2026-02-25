"""Test all possible RGB565 color format transformations

This script displays 8 test patterns, each using a different transformation
of the RGB565 color data. Check which one shows correct colors:
- Left column should be RED
- Middle column should be GREEN  
- Right column should be BLUE

Run this script and note which transformation number looks correct.

Usage:
    python -m px_device_interfaces.examples.color_format_test --port /dev/ttyACM0
"""

import argparse
import time

from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib


def rgb_to_bgr(rgb565):
    """Swap R and B channels: RGB -> BGR"""
    r = (rgb565 >> 11) & 0x1F
    g = (rgb565 >> 5) & 0x3F
    b = rgb565 & 0x1F
    return (b << 11) | (g << 5) | r


def byte_swap(rgb565):
    """Swap byte order"""
    return ((rgb565 & 0xFF) << 8) | ((rgb565 >> 8) & 0xFF)


def create_test_bitmap(transform_id):
    """Create a 3x1 test pattern: RED | GREEN | BLUE
    Apply transformation based on transform_id:
    0: No transformation (raw RGB565)
    1: BGR channel swap
    2: Byte swap
    3: BGR + Byte swap
    4: Invert colors
    5: Invert + BGR
    6: Invert + Byte swap
    7: Invert + BGR + Byte swap
    """
    red = 0xF800
    green = 0x07E0
    blue = 0x001F
    
    colors = [red, green, blue]
    
    # Apply transformation
    if transform_id in [1, 3, 5, 7]:  # BGR variants
        colors = [rgb_to_bgr(c) for c in colors]
    
    if transform_id in [2, 3, 6, 7]:  # Byte swap variants
        colors = [byte_swap(c) for c in colors]
    
    if transform_id in [4, 5, 6, 7]:  # Invert variants
        colors = [c ^ 0xFFFF for c in colors]
    
    # Create 30x30 blocks for each color
    bitmap = bytearray()
    for _ in range(20):  # 30 rows
        for color in colors:
            for _ in range(30):  # 30 pixels per color
                bitmap.extend(color.to_bytes(2, "little"))
    
    return bitmap


def main():
    parser = argparse.ArgumentParser(description="Test RGB565 color transformations")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate")
    args = parser.parse_args()
    
    cfg = USBTransportConfig(port=args.port, baud=args.baud, debug=False)
    gpio = GPIO_Lib(transport_config=cfg, require_ack_on_send=True, send_ack_timeout=1)
    
    gpio.start()
    gpio.sync()
    time.sleep(0.5)
    
    # Setup display (same as st7735_spi_demo)
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
    
    lcd.set_backlight(True)
    lcd.set_rotation(0)  # Portrait
    lcd.clear()
    
    print("\nDisplaying 8 color transformation tests...")
    print("Each test shows: RED | GREEN | BLUE (3 columns, 30px each)")
    print("\nNote which transformation number shows correct colors:\n")
    
    transform_names = [
        "0: RGB565 (no transform)",
        "1: BGR565 (channel swap)",
        "2: RGB565 byte swapped",
        "3: BGR565 byte swapped",
        "4: RGB565 inverted",
        "5: BGR565 inverted",
        "6: RGB565 inverted+byte swap",
        "7: BGR565 inverted+byte swap",
    ]
    
    y_pos = 0
    for i in range(8):
        print(f"  {transform_names[i]}")
        bitmap = create_test_bitmap(i)
        lcd.write_bitmap(bitmap, x=0, y=y_pos, width=90, height=20)
        y_pos += 20
        time.sleep(0.3)
    
    gpio.await_send_empty()
    
    print("\nTest complete!")
    print("Which transformation (0-7) shows the CORRECT colors?")
    print("Please report the number where:")
    print("  - Left column is RED")
    print("  - Middle column is GREEN")
    print("  - Right column is BLUE")
    
    gpio.stop()


if __name__ == "__main__":
    main()
