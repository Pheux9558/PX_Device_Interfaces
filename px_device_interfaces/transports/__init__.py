from __future__ import annotations

from typing import Any

from .base import BaseTransport
from .base import BaseTransportConfig
from .mock import MockTransport
from .usb import USBTransport
from .opcua import OPCUATransport


def get_transport_config_class(transport_type: str):
    """Return the transport config dataclass for a given transport type, or None.

    Useful for CLIs or interactive help. Example: `USB` -> `USBTransportConfig`.
    """
    t = (transport_type or "").upper()
    if t == "MOCK":
        from .mock import MockTransportConfig

        return MockTransportConfig
    if t == "USB":
        from .usb import USBTransportConfig

        return USBTransportConfig
    if t in ("OPCUA", "OPC-UA", "OPCUA_CLIENT"):
        from .opcua import OPCUATransportConfig

        return OPCUATransportConfig
    return None


def list_transport_types() -> list[str]:
    """Return supported transport type identifiers."""
    return ["USB", "MOCK", "OPCUA"]


__all__ = ["BaseTransport", "BaseTransportConfig", "MockTransport", "USBTransport", "OPCUATransport"]
