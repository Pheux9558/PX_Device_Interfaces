from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import ClassVar, Optional


@dataclass
class BaseTransportConfig:
    """Base configuration object for transports.

    This class serves as a base for specific transport configurations.
    Subclasses should implement the `create_transport` method to return
    an instance of the corresponding transport.
    """
    # Needed for subclassing
    transport_type: ClassVar[str] = "BASE"  # Rename in subclasses
    debug: bool = False
    timeout: float = 0.1
    auto_io: bool = True

    # Optional common fields
    # Hardware-specific fields should be added in subclasses

    def create_transport(self) -> "BaseTransport":
        """Create and return an instance of the corresponding transport."""
        raise NotImplementedError("Subclasses must implement create_transport method.")
        # return BaseTransport()  # Placeholder; subclasses should return specific transport instances
        # Example:
        # return USBTransport(port=self.port, baud=self.baud, timeout=self.timeout, debug=self.debug)


class BaseTransport(ABC):
    """Abstract transport interface.

    Implementations should be non-blocking for `send` and provide a
    `receive` method to fetch incoming data (or return None).
    `receive_bytes` is provided to get raw bytes when needed.

    The `connect` and `disconnect` methods manage the transport state,
    and `is_connected` indicates the current connection status.

    Transport implementations should also provide a `scan` classmethod
    to discover available devices of that transport type and return a list
    of dictionaries with `type` and `settings` keys. Settings dicts should
    be compatible with the transport constructor.

    Custom functionality (e.g. specific read/write methods) can be added
    in subclasses as needed. Configuration functions can also be added
    to set transport-specific parameters.
    """
    @abstractmethod
    def __init__(self) -> None:
        """Initialize the transport."""
        
    @abstractmethod
    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages if debugging is enabled."""

    @abstractmethod
    def set_debug_function(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """

    @abstractmethod
    def connect(self) -> bool:
        """Open the transport connection. Return True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the transport connection."""

    @abstractmethod
    def send(self, data: str | bytes) -> None:
        """Send data to the remote endpoint. If not connected, raise RuntimeError."""

    @abstractmethod
    def receive(self) -> Optional[str]:
        """Attempt to receive data. If no data available return None. If not connected, raise RuntimeError."""

    @abstractmethod
    def receive_bytes(self) -> Optional[bytes]:
        """Attempt to receive data as bytes. If no data available return None. If not connected, raise RuntimeError."""

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
