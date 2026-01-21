from __future__ import annotations

import threading
from typing import Optional, Dict, Any
import time

from .base import BaseTransport


class USBTransport(BaseTransport):
    """Serial (USB) transport using pyserial.

    Settings accepted via `settings` dict passed from the factory:
    - `port`: serial device path (required)
    - `baud`: baud rate (default: 115200)
    - `timeout`: read timeout in seconds (default: 0.1)
    """

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        s = settings or {}
        self.port = s.get("port")
        self.baud = int(s.get("baud", 115200))
        self.timeout = float(s.get("timeout", 0.1))
        # optional debug flag to print hex dumps of sent/received data
        self.debug = bool(s.get("debug", False))

        self._serial = None
        self._lock = threading.RLock()
        self._connected = False

    def connect(self) -> bool:
        if not self.port:
            raise ValueError("USBTransport requires 'port' setting")
        try:
            import serial

            with self._lock:
                self._serial = serial.Serial(self.port, baudrate=self.baud, timeout=self.timeout)
                # Give Arduino a short time to reset and the bootloader to finish
                # so initial configuration packets aren't lost. Then flush input.
                try:
                    # short delay to allow serial open to settle; handshake will
                    # ensure readiness so this can be small
                    time.sleep(0.1)
                    if hasattr(self._serial, "reset_input_buffer"):
                        self._serial.reset_input_buffer()
                    else:
                        # older pyserial
                        try:
                            self._serial.flushInput()
                        except Exception:
                            pass
                except Exception:
                    pass
                self._connected = True
            return True
        except Exception:
            # do not raise here; callers can inspect is_connected
            self._serial = None
            self._connected = False
            return False

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self._serial and getattr(self._serial, "is_open", True):
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            self._connected = False

    def send(self, data: str | bytes) -> None:
        if not self._serial:
            raise RuntimeError("USBTransport not connected")
        payload = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
        if self.debug:
            try:
                print(f"USBTransport send(hex): {payload.hex()}")
            except Exception:
                print(f"USBTransport send(repr): {payload!r}")
        with self._lock:
            self._serial.write(payload)

    def receive(self, timeout: float = 0.0) -> Optional[str]:
        if not self._serial:
            return None
        # if timeout specified, do a blocking read with that timeout
        try:
            raw = None
            if timeout and timeout > 0:
                old = getattr(self._serial, "timeout", None)
                self._serial.timeout = timeout
                try:
                    raw = self._serial.read_until()
                finally:
                    if old is not None:
                        self._serial.timeout = old
            else:
                # non-blocking: read available bytes
                n = getattr(self._serial, "in_waiting", 0)
                if not n:
                    return None
                raw = self._serial.read(n)

            if not raw:
                return None
            if isinstance(raw, (bytes, bytearray)) and self.debug:
                try:
                    print(f"USBTransport recv(hex): {raw.hex()}")
                except Exception:
                    print(f"USBTransport recv(repr): {raw!r}")
            # decode for backwards compatibility
            if isinstance(raw, (bytes, bytearray)):
                try:
                    return raw.decode(errors="replace").rstrip("\r\n")
                except Exception:
                    return None
            return str(raw)
        except Exception:
            return None

    def receive_bytes(self, timeout: float = 0.0) -> Optional[bytes]:
        """Return raw bytes from the serial device.

        This complements `receive()` which returns decoded text for
        backwards compatibility. `GPIO_Lib` should use `receive_bytes`.
        """
        if not self._serial:
            return None
        try:
            if timeout and timeout > 0:
                old = getattr(self._serial, "timeout", None)
                self._serial.timeout = timeout
                try:
                    raw = self._serial.read_until()
                finally:
                    if old is not None:
                        self._serial.timeout = old
            else:
                n = getattr(self._serial, "in_waiting", 0)
                if not n:
                    return None
                raw = self._serial.read(n)

            if isinstance(raw, (bytes, bytearray)) and self.debug:
                try:
                    print(f"USBTransport recv_bytes(hex): {raw.hex()}")
                except Exception:
                    print(f"USBTransport recv_bytes(repr): {raw!r}")

            return raw if raw else None
        except Exception:
            return None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected)

    @classmethod
    def scan(cls) -> list[dict]:
        """Discover serial ports using pyserial's list_ports.

        Returns a list of dicts: {"type": "USB", "settings": {"port": <device>}, "description": <desc>}
        """
        try:
            from serial.tools import list_ports

            out = []
            for p in list_ports.comports():
                out.append({"type": "USB", "settings": {"port": p.device, "baud": 115200}, "description": p.description})
            return out
        except Exception:
            return []