

import time
from px_device_interfaces import GPIO_Lib
from px_device_interfaces.transports.usb import USBTransportConfig


def test_real_device():
    """Test matrix on real device."""
    print("Testing Arduino Uno R4 LED Matrix\n")
    # Connect to device
    print("Connecting to device on /dev/ttyACM0...")
    config = USBTransportConfig(port="/dev/ttyACM0", baud=921600, debug=False)
    gpio_lib = GPIO_Lib(transport_config=config)

    try:
        if not gpio_lib.start():
            return
        # Create matrix instance
        matrix = gpio_lib.Display.DisplayUNO_R4_MATRIX(gpio_lib)
            
        # Setup
        matrix.setup()

        # # loop through all animations with a delay in between
        # print("Testing animations...")
        # for anim in matrix.Animation:
        #     print(f"  Starting {anim.name} animation...")
        #     matrix.show_animation(anim, speed=100, play=True)
        #     print("✓ Animation started\n")
        #     time.sleep(5)


        # # loop through all frames
        # print("Testing animation frames...")
        # for frame in matrix.Frame:
        #     print(f"  Showing frame {frame.name}...")
        #     matrix.show_frame(frame)
        #     print("✓ Frame shown\n")
        #     time.sleep(2)

        matrix.write_text("Pheux!", speed=100)
        time.sleep(5)


        # bitmap 12 x 8
        bitmaps = [
            [
                0b111111111111,
                0b100000000001,
                0b101111111101,
                0b101000000101,
                0b101011110101,
                0b101000000101,
                0b100000000001,
                0b111111111111,
            ],
            [
                0b000000000000,
                0b011111111110,
                0b010000000100,
                0b010111111100,
                0b010100000100,
                0b010111111100,
                0b010000000100,
                0b011111111110,
            ],
            [
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
            ],
            [
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
            ],
        ]

        cool_animation = [
            # frame 0 – thick border
            [
                0b111111111111,
                0b100000000001,
                0b101111111101,
                0b101000000101,
                0b101011110101,
                0b101000000101,
                0b100000000001,
                0b111111111111,
            ],
            # frame 1 – inverted border
            [
                0b000000000000,
                0b011111111110,
                0b010000000100,
                0b010111111100,
                0b010100000100,
                0b010111111100,
                0b010000000100,
                0b011111111110,
            ],
            # frame 2 – checkerboard A
            [
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
            ],
            # frame 3 – checkerboard B
            [
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
                0b010101010101,
                0b101010101010,
            ],
            # frame 4 – expanding square
            [
                0b111100001111,
                0b111100001111,
                0b111100001111,
                0b000011110000,
                0b000011110000,
                0b111100001111,
                0b111100001111,
                0b111100001111,
            ],
            # frame 5 – contracting square
            [
                0b000011110000,
                0b000011110000,
                0b111100001111,
                0b111100001111,
                0b111100001111,
                0b000011110000,
                0b000011110000,
                0b111100001111,
            ],
            # frame 6 – diagonal blocks A
            [
                0b001100110011,
                0b001100110011,
                0b110011001100,
                0b110011001100,
                0b001100110011,
                0b001100110011,
                0b110011001100,
                0b110011001100,
            ],
            # frame 7 – diagonal blocks B
            [
                0b110011001100,
                0b110011001100,
                0b001100110011,
                0b001100110011,
                0b110011001100,
                0b110011001100,
                0b001100110011,
                0b001100110011,
            ],
        ]
        
        print("Testing animation with custom bitmap...")
        matrix.set_custom_animation(0, cool_animation, loop=True)
        matrix.show_custom_animation(0, speed=255)  # 100ms per frame
        gpio_lib.await_send_empty()
        time.sleep(5)

        
        # Stop animation            
        print("Stopping animation...")

        matrix.clear()

    finally:
        gpio_lib.stop()




if __name__ == "__main__":
    test_real_device()

