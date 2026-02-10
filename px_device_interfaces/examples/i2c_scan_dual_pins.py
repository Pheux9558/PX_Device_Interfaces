import time
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib


PORT = "/dev/ttyACM0"
BAUD = 115200

# Add any candidate pin pairs here. Each entry is (pin_a, pin_b).
CANDIDATE_PAIRS = [(43, 44)]
TRY_BOTH_DIRECTIONS = True


def scan_with_pins(sda: int, scl: int) -> list[int]:
    config = USBTransportConfig(port=PORT, baud=BAUD, debug=False)
    gpio = GPIO_Lib(transport_config=config)
    gpio.start()

    i2c = GPIO_Lib.I2C(gpio_lib=gpio, clock_pin=scl, data_pin=sda)
    i2c.setup()

    # Give the bus a moment to settle
    time.sleep(0.05)
    addrs = i2c.full_address_scan()

    gpio.await_send_empty()
    gpio.stop()
    return addrs


def build_scan_pairs() -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for pin_a, pin_b in CANDIDATE_PAIRS:
        pairs.append((pin_a, pin_b))
        if TRY_BOTH_DIRECTIONS and pin_a != pin_b:
            pairs.append((pin_b, pin_a))
    return pairs


def main() -> list[tuple[int, int, list[int]]]:
    results: list[tuple[int, int, list[int]]] = []
    pairs = build_scan_pairs()

    for idx, (sda, scl) in enumerate(pairs, start=1):
        print("Scan %d: SDA=GPIO%d, SCL=GPIO%d" % (idx, sda, scl))
        addrs = scan_with_pins(sda, scl)
        print("Found:", [hex(a) for a in addrs])
        if addrs:
            results.append((sda, scl, addrs))

    if results:
        print("\nDetected I2C devices:")
        for sda, scl, addrs in results:
            hex_addrs = [hex(a) for a in addrs]
            print("SDA=GPIO%d SCL=GPIO%d -> %s" % (sda, scl, hex_addrs))
    else:
        print("\nNo I2C devices detected. Check wiring/power or try a slower I2C frequency.")

    return results


if __name__ == "__main__":
    main()
