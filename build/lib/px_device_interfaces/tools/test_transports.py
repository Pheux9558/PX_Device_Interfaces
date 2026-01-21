import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path so `python` package imports work during pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from px_device_interfaces.transports import MockTransport


def test_mock_transport_loopback():
    # call using the new parameter name semantics (positional is supported)
    t = MockTransport(loopback=True)
    assert not t.is_connected
    assert t.connect() is True
    assert t.is_connected

    # send a message and receive via loopback
    t.send("ping")
    # allow a tiny amount of time for queueing
    time.sleep(0.01)
    r = t.receive(timeout=0.1)
    assert r == "ping"

    sent = t.pop_sent()
    assert sent == ["ping"]

    t.disconnect()
    assert not t.is_connected
