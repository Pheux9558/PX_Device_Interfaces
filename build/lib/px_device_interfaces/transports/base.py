from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BaseTransport(ABC):
    """Abstract transport interface.

    Implementations should be non-blocking for `send` and provide a
    `receive` method to fetch incoming data (or return None).
    """

    @abstractmethod
    def connect(self) -> bool:
        """Open the transport connection. Return True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the transport connection."""

    @abstractmethod
    def send(self, data: str | bytes) -> None:
        """Send data to the remote endpoint."""

    @abstractmethod
    def receive(self, timeout: float = 0.0) -> Optional[bytes | str]:
        """Attempt to receive data. If no data available return None."""

    def receive_bytes(self, timeout: float = 0.0) -> Optional[bytes]:
        """Attempt to receive data as bytes. If no data available return None."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Transport connection status."""

    @classmethod
    @abstractmethod
    def scan(cls) -> list[dict]:
        """Discover available devices for this transport type.

        Returns a list of dictionaries describing found devices. Each entry
        should include at least a `type` string and a `settings` dict that
        can be passed to `create_transport(transport_type, settings)`.
        Example: {"type": "USB", "settings": {"port": "/dev/ttyUSB0"}}
        """
