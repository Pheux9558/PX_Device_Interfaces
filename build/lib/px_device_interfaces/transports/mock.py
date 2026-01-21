from __future__ import annotations

import queue
import threading
from typing import Optional

from .base import BaseTransport


class MockTransport(BaseTransport):
    """A simple in-process transport useful for unit tests.

    Behavior:
    - `send` appends to an internal sent list and places the value into
      an incoming queue (loopback) if `loopback` is True.
    - `receive` pulls from the incoming queue and returns strings.
    - `connect`/`disconnect` toggle `is_connected`.
    """

    def __init__(self, *, loopback: bool = True) -> None:
        self._loopback = loopback
        # store raw bytes in incoming queue (compat: receive() decodes)
        self._incoming: "queue.Queue[bytes]" = queue.Queue()
        # keep a list of raw sent payloads for inspection
        self._sent: list[bytes] = []
        self._connected = False
        self._lock = threading.RLock()

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

    def receive(self, timeout: float = 0.0) -> Optional[str]:
        """Return a text-decoded message if possible (keeps compatibility)."""
        try:
            raw = self._incoming.get(timeout=timeout) if timeout and timeout > 0 else self._incoming.get_nowait()
            try:
                return raw.decode(errors="replace")
            except Exception:
                return None
        except Exception:
            return None

    def receive_bytes(self, timeout: float = 0.0) -> Optional[bytes]:
        """Return raw bytes from the incoming queue (preferred for binary protocols)."""
        try:
            return self._incoming.get(timeout=timeout) if timeout and timeout > 0 else self._incoming.get_nowait()
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
