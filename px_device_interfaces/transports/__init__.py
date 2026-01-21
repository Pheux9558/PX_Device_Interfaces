from __future__ import annotations

from typing import Any, Dict

from .base import BaseTransport
from .mock import MockTransport
from .usb import USBTransport
from px_device_interfaces import settings_manager


def create_transport_for_device(device_name: str) -> BaseTransport:
    """Create a transport for a device using settings from `settings_manager`.

    The device settings must include a top-level `type` key (e.g. "USB").
    """
    s = settings_manager.load_connection_settings(device_name)
    ttype = s.get("type")
    if not ttype:
        raise ValueError(f"no transport type configured for device '{device_name}'")
    k = str(ttype).strip().upper()
    if k == "MOCK":
        return MockTransport(loopback=bool(s.data.get("loopback", True)))
    if k == "USB":
        return USBTransport(s.data)
    raise ValueError(f"unknown transport type: {ttype}")


__all__ = ["BaseTransport", "MockTransport", "create_transport_for_device"]
