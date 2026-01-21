import sys

import time
from pathlib import Path

# Ensure repo root is on sys.path so `python` package imports work during pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from px_device_interfaces.connection_organiser_adapter import ConnectionOrganiserAdapter
from px_device_interfaces.settings_manager import Settings, save_connection_settings


def test_connection_organiser_adapter_queue_stress():
    """Stress test: enqueue a large number of commands and ensure all are received.

    Uses `MockTransport` loopback to avoid hardware.
    """
    N = 500
    # ensure a settings file exists for `temp` device so adapter can create transport
    s = Settings(program="Connection_Organiser", device="temp", data={"type": "MOCK", "loopback": True})
    save_connection_settings("temp", s)

    co = ConnectionOrganiserAdapter("temp", interactive=False, debug=False)
    co.start()
    # give threads a moment to start
    time.sleep(0.02)

    for i in range(N):
        co.send_command(f"MSG_{i}")

    received = []
    start = time.time()
    timeout = 5.0
    while len(received) < N and (time.time() - start) < timeout:
        msg = co.receive_nowait()
        if msg is not None:
            received.append(msg)
        else:
            time.sleep(0.005)

    co.stop()

    assert len(received) == N, f"expected {N} messages, got {len(received)}"
