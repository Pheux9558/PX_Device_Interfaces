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
from px_device_interfaces.GPIO_Lib import GPIO_Lib, CMD_LCD_WRITE_BITMAP, CMD_DIGITAL_READ


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
        pkt = gpio._build_packet(CMD_LCD_WRITE_BITMAP, payload)
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
