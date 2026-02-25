import time
import serial
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, ClassVar

from .base import BaseTransport, BaseTransportConfig


@dataclass
class USBTransportConfig(BaseTransportConfig):
    """Configuration for `USBTransport`.

    Fields:
      - `port`: serial device path (e.g. COM3 or /dev/ttyACM0)
      - `baud`: baud rate
      - `timeout`: read timeout in seconds
      - `debug`: enable debug prints
    """
    transport_type: ClassVar[str] = "USB"

    port: Optional[str] = None
    baud: int = 921600
    timeout_connect: float = 5.0
    debug: bool = False
    auto_io: bool = True
    reset_on_start: bool = True

    def create_transport(self) -> "USBTransport":
        return USBTransport(port=self.port, baud=self.baud, config=self)

    def help(self) -> str:
        return (
            "\nUSBTransportConfig fields:\n"
            "  - port: serial device path (e.g. COM3 or /dev/ttyACM0)\n"
            "  - baud: baud rate\n"
            "  - timeout_connect: connection timeout in seconds\n"
            "  - debug: enable debug prints\n"
            "  - auto_io: whether to automatically handle I/O\n"
            "  - reset_on_start: whether to reset the device on start\n"
        )
    
    @classmethod
    def scan(cls) -> list[dict]:
        """Discover serial ports using pyserial's list_ports.
        Returns a list of dicts: {"type": "USB", "settings": {"port": <device>}, "description": <desc>}
        """
        try:
            from serial.tools import list_ports

            out = []
            for p in list_ports.comports():
                if not p.description or p.description == 'n/a':
                    continue
                out.append({"type": "USB", "settings": {"port": p.device, "baud": 921600}, "description": p.description})
            return out
        except Exception:
            return []


class USBTransport(BaseTransport):
    """Serial (USB) transport using pyserial.

    Settings accepted from the factory or from stanalone constructor:
    - `port`: serial device path (required)
    - `baud`: baud rate (default: 115200)
    - `timeout_connect`: connection timeout in seconds (default: 5.0)
    - `debug`: enable debug prints (default: True)

    This transport sends and receives raw bytes. For backwards compatibility,
    the `receive()` method decodes bytes to text. New code should use `receive_bytes()`.
    
    Debug messages include timestamps in ISO 8601 format with milliseconds.
    Additional configuration method:
    - `setDebugFunction(debug_function)`: set a custom debug function to handle debug messages.
    - `setTimeOut(timeout)`: set the read timeout in seconds.

    Class method:
    - `scan()`: discover available serial ports using pyserial's list_ports.
    """

    def __init__(self, port: Optional[str] = None, baud: Optional[int] = 921600, config: Optional[USBTransportConfig] = None) -> None:
        """Initialize USBTransport with explicit parameters."""
        self.config = config
        self.port = config.port if config and config.port is not None else port
        self.baud = config.baud if config and config.baud is not None else (baud if baud is not None else 921600)
        self.timeout_connect = config.timeout_connect if config and config.timeout_connect is not None else 5.0
        self.debug = config.debug if config and config.debug is not None else False
        self._serial = None
        self._lock = threading.RLock()
        self._connected = False

    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages if debugging is enabled via stdout."""
        timestamp = timestamp or datetime.now().isoformat(timespec='milliseconds')
        if self.debug:
            print(f"{timestamp} - {msg}")
    
    # Function to send debug messages to external function
    def set_debug_function(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function

    def connect(self) -> bool:
        """Open the serial port connection. Return True on success."""
        if not self.port:
            raise ValueError("USBTransport requires 'port' setting")
        if not self.baud:
            raise ValueError("USBTransport requires 'baud' setting")
        try:
            with self._lock:
                self._serial = serial.Serial(self.port, baudrate=self.baud, timeout=self.timeout_connect)
                # Give Arduino a short time to reset and the bootloader to finish
                # so initial configuration packets aren't lost. Then flush input.
                # short delay to allow serial open to settle; handshake will
                # ensure readiness so this can be small
                time.sleep(0.1)
                self._serial.reset_input_buffer()
                self._serial.flush()
                self._connected = True
            return True
        except Exception as e:
            # do not raise here; callers can inspect is_connected
            self.log_debug_message(f"USBTransport failed to connect to {self.port} at baud {self.baud}: {e}")
            self._serial = None
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the serial port connection."""
        if not self._serial:
            raise RuntimeError("USBTransport not connected")

        with self._lock:
            try:
                if getattr(self._serial, "is_open", True):
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            self._connected = False

    def send(self, data: str | bytes) -> None:
        """Send data to the serial port. Encode to bytes if needed."""
        if not self._serial or not self.is_connected:
            raise RuntimeError("USBTransport not connected")
        
        payload = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
        if self.debug:
            self.log_debug_message(f"USBTransport -> send({payload})", datetime.now().isoformat(timespec='milliseconds'))
        with self._lock:
            self._serial.write(payload)

    def receive(self, length: Optional[int] = None) -> Optional[str]:
        """Receive data from the serial port. Return decoded string or None."""

        print("###NO LONGER USED - USE RECEIVE_BYTES INSTEAD AND DECODE YOURSELF###")
        if not self._serial or not self.is_connected:
            raise RuntimeError("USBTransport not connected")    
        
        raw = None

        # if timeout specified, do a blocking read with that timeout
        try:
            n = getattr(self._serial, "in_waiting", 0)
            if not n:
                return None
            raw = self._serial.read(n)
        except Exception:
            return None

        try:
            if not raw:
                return None
            if isinstance(raw, (bytes, bytearray)) and self.debug:
                if not raw == b'' and not raw == b'\r\n':
                    self.log_debug_message(f"USBTransport <- recv({raw})", datetime.now().isoformat(timespec='milliseconds'))
            # decode for backwards compatibility
            if isinstance(raw, (bytes, bytearray)):
                try:
                    return raw.decode(errors="replace").rstrip("\r\n")
                except Exception:
                    return None
            return str(raw)
        except Exception:
            return None

    def receive_bytes(self) -> Optional[bytes]:
        """Return raw bytes from the serial device.

        This complements `receive()` which returns decoded text for
        backwards compatibility. `GPIO_Lib` should use `receive_bytes`.
        """
        if not self._serial or not self.is_connected:
            raise RuntimeError("USBTransport not connected")    

        try:
            n = getattr(self._serial, "in_waiting", 0)
            if not n:
                return None
            raw = self._serial.read(n)

            if isinstance(raw, (bytes, bytearray)) and self.debug:
                if not raw == b'' and not raw == b'\r\n':
                    self.log_debug_message(f"USBTransport <- recv_bytes({raw})", datetime.now().isoformat(timespec='milliseconds'))

            return raw if raw else None
        except Exception:
            return None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected)
