from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
import threading

from opcua import Client
from opcua import ua
import logging

from .base import BaseTransport


from dataclasses import dataclass

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
    auto_io: bool = False

    def create_transport(self) -> "OPCUATransport":
        return OPCUATransport(opcua_endpoint=self.opcua_endpoint, config=self)

    def help(self) -> str:
        return (
            "\nOPCUATransportConfig fields:\n"
            "  - opcua_endpoint: server endpoint (e.g. 'opc.tcp://host:4840')\n"
            "  - default_node: NodeId to use by default\n"
            "  - username: optional username for authentication\n"
            "  - password: optional password for authentication\n"
            "  - timeout: request timeout seconds\n"
            "  - debug: enable debug prints\n"
            "  - auto_io: whether to automatically handle I/O\n"
        )

class OPCUATransport:
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



    def __init__(self, opcua_endpoint: Optional[str] = None, config: Optional[OPCUATransportConfig] = None) -> None:
        if config is not None:
            self._endpoint = config.opcua_endpoint
            self._default_node = config.default_node
            self._username = config.username
            self._password = config.password
            self._timeout = config.timeout
            self.auto_io = config.auto_io
            self.debug = config.debug
        else:
            self._endpoint = opcua_endpoint
            self._default_node = None
            self._username = None
            self._password = None
            self.auto_io = False
            self._timeout = 4.0
            self.debug = True
        
        

        self._connected = False
        self._lock = threading.RLock()

    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages if debugging is enabled via stdout."""
        timestamp = timestamp or datetime.datetime.now().isoformat(timespec='milliseconds')
        if self.debug:
            print(f"{timestamp} - {msg}")

    # Function to send debug messages to external function
    def set_debug_function(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function

    def set_time_out(self, timeout: float) -> None:
        """Set the request timeout in seconds."""
        with self._lock:
            self._timeout = timeout
            self._client.session_timeout = int(self._timeout * 1000)
    
    def connect(self) -> bool:
        if not self._endpoint:
            raise RuntimeError("OPCUATransport.connect called without endpoint configured")
        if self.is_connected:
            raise RuntimeError("OPCUATransport.connect called when already connected")

        with self._lock:
            try:
                self._client = Client(self._endpoint)
                self._client.session_timeout = int(self._timeout * 1000)
                # set credentials if provided (left optional for anonymous)
                if self._username is not None and self._password is not None:
                    self._client.set_user(self._username)
                    self._client.set_password(self._password)
                self._client.connect()
                self._connected = True
                return True
            except Exception as e:
                logging.getLogger(__name__).warning("OPCUATransport.connect failed: %s", e)
                self._connected = False
                return False

    def disconnect(self) -> None:
        if not self.is_connected:
            raise RuntimeError("OPCUATransport.disconnect called when not connected")
        with self._lock:
            try:
                self._client.disconnect()
            finally:
                self._connected = False

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._connected)

    
    # Convenience helpers (not part of BaseTransport)
    def read(self, nodeid: str) -> Any:
        v = self._client.get_node(nodeid).get_value()
        self.log_debug_message(f"OPCUA.read: nodeid={nodeid} value={v}")
        # normalize common container types

        return v

    def write(self, nodeid: str, value: Any) -> None:
        try:
            if self.getDataType(value) != self.getNodeDataType(nodeid):
                raise TypeError(f"OPCUA.write: data type mismatch. Node {nodeid} expects {self.getNodeDataType(nodeid)}, got {self.getDataType(value)}")
            client_node = self._client.get_node(nodeid)
            print(f"Writing to node {nodeid} value {value} of type {type(value)}")
            # Let the opcua library pick an appropriate Variant/encoding for
            # the provided Python value (scalars, lists, bytes, etc.). Creating
            # explicit Variants has caused server errors for some combinations,
            # so try the simple `set_value(value)` first and fall back to
            # alternate encodings when necessary.
            try:
                client_node.set_value(value)
                return
            except Exception as e:

                # Try to query the node's expected UA VariantType and retry using it
                try:
                    node_variant_type = client_node.get_data_type_as_variant_type()
                    try:
                        # Ask the library to encode using the node's variant type
                        client_node.set_value(value, varianttype=node_variant_type)
                        return
                    except Exception as e_vt:
                        # If node expects ByteString, try bytes
                        if node_variant_type == ua.VariantType.ByteString and isinstance(value, (list, bytearray, bytes)):
                            try:
                                client_node.set_value(bytes(value))
                                return
                            except Exception as e_bs:
                                pass
                        # If node expects Byte (often an array of bytes), try sending as byte array Variant
                        if node_variant_type == ua.VariantType.Byte and isinstance(value, list) and all(isinstance(x, int) and 0 <= x <= 255 for x in value):
                            try:
                                # Explicitly mark as an array of bytes
                                dv = ua.DataValue(ua.Variant(list(value), ua.VariantType.Byte, is_array=True))
                                client_node.set_attribute(ua.AttributeIds.Value, dv)
                                return
                            except Exception as e_bv:
                                pass
                        # If node expects boolean array, try bool conversion
                        if node_variant_type == ua.VariantType.Boolean and isinstance(value, list):
                            try:
                                client_node.set_value([bool(x) for x in value])
                                return
                            except Exception as e_b:
                                pass
                except Exception as e_q:
                    pass

                # Fallback 1: if value looks like a list of 0/1, try boolean array
                if isinstance(value, list) and all(isinstance(x, int) and x in (0, 1) for x in value):
                    try:
                        bools = [bool(x) for x in value]
                        client_node.set_value(bools)
                        return
                    except Exception as e2:
                        pass

                # Fallback 2: try ByteString/bytearray for 0..255 integer lists
                if isinstance(value, list) and all(isinstance(x, int) and 0 <= x <= 255 for x in value):
                    try:
                        client_node.set_value(bytearray(value))
                        return
                    except Exception as e2:
                        pass

                # Fallback 3: attempt explicit Variant with Int16 element type
                # (servers sometimes expect a specific numeric array UA type).
                try:
                    dv = ua.DataValue(ua.Variant(value, ua.VariantType.Int16))
                    client_node.set_attribute(ua.AttributeIds.Value, dv)
                    return
                except Exception as e2:
                    pass

                # No suitable fallback succeeded — if the server explicitly
                # rejects this write format, treat it as non-fatal: log and
                # skip the write (some servers disallow writing timestamps
                # or specific combinations). Otherwise re-raise.
                errstr = str(e)
                if "BadWriteNotSupported" in errstr or "BadWriteNotSupported" in repr(e):
                    self.log_debug_message(f"OPCUA.write: server refused write (not supported) [{e}] — skipping")
                raise e
        except Exception as e:
            self.log_debug_message(f"OPCUA.write: error [{e}]")
            raise e

    def getNodeDataType(self, nodeid: str):
        val = self.read(nodeid)
        return type(val)
    
    def getDataType(self, data: Any):
        return type(data)
       

    def call_method(self, object_nodeid: str, method_nodeid: str, *args: Any) -> Any:
        return self._client.get_node(object_nodeid).call_method(method_nodeid, *args)

    @classmethod
    def scan(cls) -> List[Dict]:
        """Return an empty list — OPC UA discovery requires network/endpoint input.

        Higher-level code should populate discovery results with known endpoints.
        """
        return []
