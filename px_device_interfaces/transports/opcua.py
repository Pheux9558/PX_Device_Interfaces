from __future__ import annotations

from typing import Any, Dict, List, Optional
import threading

from opcua import Client
from opcua import ua
import logging

from .base import BaseTransport


from dataclasses import dataclass


class OPCUATransport(BaseTransport):
    """A simple OPC UA client transport.

    Settings accepted (either via `settings` dict or constructor kwargs):
    - endpoint: OPC UA server endpoint (e.g. "opc.tcp://host:4840")
    - default_node: NodeId string to use for generic send/receive
    - username/password: optional credentials (left unused if None)
    - timeout: request timeout in seconds

    This transport provides convenience helpers (`read`, `write`, `call_method`)
    while implementing the `BaseTransport` interface. `send`/`receive` map
    to `write`/`read` on the configured `default_node`.
    """


@dataclass
class OPCUATransportConfig:
    """Configuration object for `OPCUATransport`.

    Fields:
      - `opcua_endpoint`: server endpoint
      - `default_node`: NodeId to use by default
      - `username`/`password`: optional credentials
      - `timeout`: request timeout seconds
      - `debug`: enable debug prints
    """
    opcua_endpoint: Optional[str] = None
    default_node: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: float = 4.0
    debug: bool = False

    def create_transport(self) -> "OPCUATransport":
        return OPCUATransport(opcua_endpoint=self.opcua_endpoint, default_node=self.default_node, username=self.username, password=self.password, timeout=self.timeout, debug=self.debug)

    def __init__(self, opcua_endpoint: Optional[str] = None, default_node: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None, timeout: Optional[float] = 4.0, debug: bool = False) -> None:
        self._endpoint = opcua_endpoint or "opc.tcp://localhost:4840"
        self._default_node = default_node
        self._username = username
        self._password = password
        self._timeout = timeout if timeout is not None else 4.0
        self.debug = debug
        self._client = Client(self._endpoint)
        self._client.session_timeout = int(self._timeout * 1000)
        # set credentials if provided (left optional for anonymous)
        if self._username is not None and self._password is not None:
            try:
                self._client.set_user(self._username)
                self._client.set_password(self._password)
            except Exception:
                # some client versions may accept credentials differently;
                # if this fails we continue and let connect() surface errors.
                pass

        self._connected = False
        self._lock = threading.RLock()

    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages if debugging is enabled via stdout."""
        timestamp = timestamp or "N/A"
        if self.debug:
            print(f"{timestamp} - {msg}")
            
    def setDebugFunction(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function

    def connect(self) -> bool:
        with self._lock:
            try:
                self._client.connect()
                self._connected = True
                return True
            except Exception as e:
                logging.getLogger(__name__).warning("OPCUATransport.connect failed: %s", e)
                self._connected = False
                return False

    def disconnect(self) -> None:
        with self._lock:
            try:
                self._client.disconnect()
            finally:
                self._connected = False

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected)

    def send(self, data: str | bytes) -> None:
        """Write `data` to the configured `default_node`.

        Raises `ValueError` if no `default_node` is configured.
        """
        if not self._default_node:
            raise ValueError("no default_node configured for send()")
        # convert bytes -> str for simple scalar writes
        val: Any
        if isinstance(data, (bytes, bytearray)):
            try:
                val = data.decode(errors="replace")
            except Exception:
                val = data
        else:
            val = data
        node = self._client.get_node(self._default_node)
        node.set_value(val)

    def receive(self) -> Optional[str]:
        """Read the value of `default_node` and return its string form.

        Returns `None` if no default node is configured or read fails.
        """
        if not self._default_node:
            return None
        try:
            node = self._client.get_node(self._default_node)
            v = node.get_value()
            # normalize common binary/array types to string for receive()
            if isinstance(v, (bytes, bytearray)):
                return v.decode(errors="replace")
            if isinstance(v, list):
                try:
                    return bytes(v).decode(errors="replace")
                except Exception:
                    return str(v)
            return str(v)
        except Exception as e:
            logging.getLogger(__name__).debug("OPCUATransport.receive read failed: %s", e)
            return None

    def receive_bytes(self) -> Optional[bytes]:
        # prefer raw read from the node where possible
        if not self._default_node:
            return None
        try:
            node = self._client.get_node(self._default_node)
            v = node.get_value()
            if isinstance(v, (bytes, bytearray)):
                return bytes(v)
            if isinstance(v, list):
                try:
                    return bytes(v)
                except Exception:
                    return None
            # fallback to text-encoded bytes
            return str(v).encode()
        except Exception as e:
            logging.getLogger(__name__).debug("OPCUATransport.receive_bytes failed: %s", e)
            return None

    # Convenience helpers (not part of BaseTransport)
    def read(self, nodeid: str) -> Any:
        v = self._client.get_node(nodeid).get_value()
        print("Read value:", v)
        # normalize common container types
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, list):
            try:
                return bytes(v)
            except Exception:
                return v
        return v

    def write(self, nodeid: str, value: Any) -> None:
        node = self._client.get_node(nodeid)
        # handle bytes specially: try ByteString first, then fall back to array
        if isinstance(value, (bytes, bytearray)):
            try:
                node.set_value(ua.Variant(bytes(value), ua.VariantType.ByteString))
                return
            except ua.UaStatusCodeError:
                # server refuses ByteString variant, try array of bytes
                try:
                    node.set_value(list(value))
                    return
                except ua.UaStatusCodeError:
                    raise
        # default path
        try:
            node.set_value(value)
        except ua.UaStatusCodeError:
            raise

    def call_method(self, object_nodeid: str, method_nodeid: str, *args: Any) -> Any:
        return self._client.get_node(object_nodeid).call_method(method_nodeid, *args)

    @classmethod
    def scan(cls) -> List[Dict]:
        """Return an empty list — OPC UA discovery requires network/endpoint input.

        Higher-level code should populate discovery results with known endpoints.
        """
        return []
