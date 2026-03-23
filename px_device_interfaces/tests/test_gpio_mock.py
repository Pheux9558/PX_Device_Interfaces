import os
import sys
import threading
import time

import pytest

# ensure repo root is on sys.path so `python.*` imports work when pytest runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from px_device_interfaces.transports.mock import MockTransport, MockTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, CMD_ST7735_WRITE_BITMAP, CMD_DIGITAL_READ


def test_mock_large_bitmap_and_response(tmp_path):
    device = "testdev"
    # create a MockTransport (no loopback - we'll push responses manually)
    mock = MockTransport(loopback=False)

    # create GPIO_Lib with a mock transport config and inject transport instance
    cfg = MockTransportConfig(loopback=False, debug=True, timeout=0.1, auto_io=False)
    gpio = GPIO_Lib(transport_config=cfg, debug_enabled=True)
    gpio._transport = mock
    mock.connect()

    # start the receive worker thread
    gpio._running = True
    gpio._recv_thread = threading.Thread(target=gpio._recv_worker, daemon=True)
    gpio._recv_thread.start()

    try:
        # configure IO (sends config frames)
        gpio.pinMode(15, "INPUT", "BTN1")
        gpio.pinMode(16, "OUTPUT", "LED1")

        # clear any sent frames recorded by MockTransport
        mock.pop_sent()

        # build and send a 256-byte bitmap frame to the transport
        payload = bytes([i & 0xFF for i in range(256)])
        pkt = gpio._build_packet(CMD_ST7735_WRITE_BITMAP, payload)
        mock.send(pkt)

        sent = mock.pop_sent(raw=True)
        assert len(sent) == 1
        sent_pkt = sent[0]
        assert isinstance(sent_pkt, (bytes, bytearray))

        # Print transmitted packet for manual verification
        hex_repr = sent_pkt.hex()
        cmd = int.from_bytes(sent_pkt[1:3], "little")
        length = int.from_bytes(sent_pkt[3:5], "little")
        chk = sent_pkt[5 + length]
        print("\n--- Transmitted packet ---")
        print(f"HEX ({len(sent_pkt)} bytes): {hex_repr}")
        print(f"CMD=0x{cmd:04X}, LEN={length}, CHK=0x{chk:02X}")
        print("--- end packet ---\n")

        # verify the 2-byte length field contains 256 (little-endian at offsets 3..4)
        assert length == 256

        # simulate device response: digital read on pin 15 = 1
        resp = gpio._build_packet(CMD_DIGITAL_READ, bytes([15, 1]))
        mock._incoming.put(resp)

        # give receive worker a moment to process
        time.sleep(0.1)

        assert "BTN1" in gpio.inputs
        assert gpio.inputs["BTN1"]["value"] == 1

    finally:
        # stop worker
        gpio._running = False
        if gpio._recv_thread is not None:
            gpio._recv_thread.join(0.2)

def test_display_write_bitmap_host_conversion():
    """Display.write_bitmap() should convert RGB565->BGR565+invert on the host before sending rows."""
    mock = MockTransport(loopback=False)
    cfg = MockTransportConfig(loopback=False, debug=True, timeout=0.1, auto_io=False)
    gpio = GPIO_Lib(transport_config=cfg, debug_enabled=True)
    gpio._transport = mock
    mock.connect()

    gpio._running = True
    gpio._recv_thread = threading.Thread(target=gpio._recv_worker, daemon=True)
    gpio._recv_thread.start()

    try:
        spi = gpio.SPI(gpio, data_pin=23, clock_pin=18)
        lcd = gpio.Display(gpio, spi, cs_pin=5, rs_pin=16, enable_pin=17, width=2, height=1)

        # clear setup frames
        mock.pop_sent()

        # 2x1 RGB565 bitmap: [red, blue]
        # red RGB565 = 0xF800 -> bytes [0x00, 0xF8]
        # blue RGB565 = 0x001F -> bytes [0x1F, 0x00]
        bmp = bytes([0x00, 0xF8, 0x1F, 0x00])
        lcd.write_bitmap(bmp, x_pos=0, y_pos=0, x_len=2, y_len=1)

        sent = mock.pop_sent(raw=True)
        row_payload = None
        for pkt in sent:
            cmd = int.from_bytes(pkt[1:3], "little")
            if cmd != CMD_ST7735_WRITE_BITMAP:
                continue
            length = int.from_bytes(pkt[3:5], "little")
            payload = pkt[5:5+length]
            if payload[2] == 2:
                row_payload = payload
                break

        assert row_payload is not None
        pixel_bytes = row_payload[5:]
        # expected converted pixels:
        # red -> rgb565 0xF800 => bgr565 0x001F ^ 0xFFFF = 0xFFE0 -> bytes [0xE0, 0xFF]
        # blue -> rgb565 0x001F => bgr565 0xF800 ^ 0xFFFF = 0x07FF -> bytes [0xFF, 0x07]
        assert pixel_bytes == bytes([0xE0, 0xFF, 0xFF, 0x07])

    finally:
        gpio._running = False
        if gpio._recv_thread is not None:
            gpio._recv_thread.join(0.2)