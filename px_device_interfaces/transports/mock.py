import queue
import threading
from dataclasses import dataclass
from typing import Optional, ClassVar

from .base import BaseTransport, BaseTransportConfig


@dataclass
class MockTransportConfig(BaseTransportConfig):
    """Configuration object for `MockTransport` used in tests.

    Fields:
      - `loopback`: whether to loop sent messages back into incoming queue
      - `debug`: enable debug prints
      - `timeout`: receive timeout seconds
    """
    transport_type: ClassVar[str] = "MOCK"
    loopback: bool = True
    debug: bool = False
    timeout: float = 0.1
    auto_io: bool = True

    def create_transport(self) -> "MockTransport":
        return MockTransport(loopback=self.loopback, debug=self.debug, timeout=self.timeout)


class MockTransport(BaseTransport):
    """A simple in-process transport useful for unit tests.

    Behavior:
    - `send` appends to an internal sent list and places the value into
      an incoming queue (loopback) if `loopback` is True.
    - `receive` pulls from the incoming queue and returns strings.
    - `connect`/`disconnect` toggle `is_connected`.
    """

    def __init__(self, *, loopback: bool | None = True, debug: bool = False, timeout: float | None = None) -> None:
        self._loopback = loopback if loopback is not None else True
        self._debug = debug
        self._timeout = timeout if timeout is not None else 0.1
        # store raw bytes in incoming queue (compat: receive() decodes)
        self._incoming: "queue.Queue[bytes]" = queue.Queue()
        # keep a list of raw sent payloads for inspection
        self._sent: list[bytes] = []
        self._connected = False
        self._lock = threading.RLock()

    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages if debugging is enabled via stdout."""
        timestamp = timestamp or "N/A"
        if self._debug:
            print(f"{timestamp} - {msg}")
    
    def set_debug_function(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function
    
    def connect(self) -> bool:
        with self._lock:
            self._connected = True
        return True

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False

    def send(self, data: str | bytes) -> None:
        # preserve raw bytes when provided; convert str -> utf-8 bytes
        b = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
        with self._lock:
            self._sent.append(bytes(b))
            if self._loopback:
                # emulate arrival at the other end (raw bytes)
                self._incoming.put(bytes(b))

    def receive(self) -> Optional[str]:
        """Return a text-decoded message if possible (keeps compatibility)."""
        try:
            raw = self._incoming.get(timeout=self._timeout) if self._timeout and self._timeout > 0 else self._incoming.get_nowait()
            try:
                return raw.decode(errors="replace")
            except Exception:
                return None
        except Exception:
            return None

    def receive_bytes(self) -> Optional[bytes]:
        """Return raw bytes from the incoming queue (preferred for binary protocols)."""
        try:
            return self._incoming.get(timeout=self._timeout) if self._timeout and self._timeout > 0 else self._incoming.get_nowait()
        except Exception:
            return None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected)

    # Test helpers
    def pop_sent(self, raw: bool = False) -> list:
        """Return a copy of sent data and clear the sent buffer.

        By default this returns decoded strings for backwards compatibility
        with tests and older code. Pass `raw=True` to receive the raw
        `bytes` values instead.
        """
        with self._lock:
            out = list(self._sent)
            self._sent.clear()
        if raw:
            return out
        decoded: list[str] = []
        for b in out:
            try:
                decoded.append(b.decode(errors="replace"))
            except Exception:
                decoded.append(str(b))
        return decoded

    @classmethod
    def scan(cls) -> list[dict]:
        """Return a minimal, test-friendly discovery result."""
        return [{"type": "MOCK", "settings": {"loopback": True}}]
