import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path so `python` package imports work during pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from px_device_interfaces.connection_organiser_adapter import ConnectionOrganiserAdapter
from px_device_interfaces.settings_manager import Settings, save_connection_settings


def test_connection_organiser_adapter_mock_roundtrip():
    # ensure a settings file exists for `temp` device so adapter can create transport
    s = Settings(program="Connection_Organiser", device="temp", data={"type": "MOCK", "loopback": True})
    save_connection_settings("temp", s)

    co = ConnectionOrganiserAdapter("temp", interactive=False, debug=False)
    assert not co.is_connected()

    co.start()
    # allow threads to start
    time.sleep(0.05)
    assert co.is_connected()

    # send a command and expect it back via loopback
    co.send_command("TEST_CMD")
    time.sleep(0.05)
    msg = co.receive_nowait()
    assert msg == "TEST_CMD"

    co.stop()
    time.sleep(0.01)
    assert not co.is_connected()
