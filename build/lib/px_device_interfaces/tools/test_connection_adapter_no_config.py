import sys
import pytest
from pathlib import Path

# Ensure repo root is on sys.path so `python` package imports work during pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from px_device_interfaces.connection_organiser_adapter import ConnectionOrganiserAdapter


def test_start_without_configuration_raises():
    # Use a device name unlikely to have configuration
    co = ConnectionOrganiserAdapter("__no_config_device__")
    with pytest.raises(RuntimeError):
        co.start()
