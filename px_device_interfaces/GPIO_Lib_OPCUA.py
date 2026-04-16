

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import threading
import time
from px_device_interfaces.transports.opcua import OPCUATransport, OPCUATransportConfig

_DEFAULT_SESSION_MARKERS: tuple = (
    "BadSessionIdInvalid",
    "BadSessionNotActivated",
    "BadSessionClosed",
    "ActivateSession has not been called",
    "session id is not valid",
)







"""
#### REWRITE ####

Editing notes for GPIO_Lib_OPCUA.py:

The input and Output arrays are maped to the same Pin
The status of the IN_SW determine the function and expacted value of the hardware pin, The value is then put in OUT_SW
    IN_SW=0 => PIN=Output pin low => OUT_SW=0 (OK); OUT_SW=8 (Fault external voltage)
    IN_SW=1 => PIN=Output pin high => OUT_SW=1 (OK); OUT_SW=9 (Fault short)
    IN_SW=2 => PIN=Input pin low => OUT_SW=2 (OK); OUT_SW=10 (Fault Input high)
    IN_SW=3 => PIN=Input pin high => OUT_SW=3 (OK); OUT_SW=11 (Fault Input low)
    IN_SW=4 => PIN=RESERVED => OUT_SW=4 (OK); OUT_SW=12 (Fault RESERVED)
    IN_SW=5 => PIN=Output pin high(SHORT) => OUT_SW=5 (OK); OUT_SW=13 (Fault no short circuit)
    IN_SW=6 => PIN=Igniore => OUT_SW=6 (OK); OUT_SW=6 (Ignore)
    IN_SW=7 => PIN=RESERVED => OUT_SW=7 (OK); OUT_SW=15 (Fault RESERVED)
When synced both Arrays should be read from the Server.
When writing => write to IN_SW
When reading => read from OUT_WS

"""

class GPIO_Lib_OPCUA:
    """GPIO_Lib_OPCUA: GPIO_Lib functionality over OPC-UA transport"""

    # region Initialization
    def __init__(self,
                 transport_config: OPCUATransportConfig,
                 debug_enabled: bool = False):
        
        self._transport_config = transport_config
        self.debug_enabled = debug_enabled

        self._running = False
        self._transport: Optional[OPCUATransport] = None


        # Mirror dictionaries explanation:
        # These mirrors are used to keep track of the last known state of the inputs and outputs
        # IN_SW_mirror holds the desired state to be written to the hardware
        # OUT_SW_mirror holds the actual state read from the hardware
        self.IN_SW_mirror: Dict[str, Dict] = {}
        self.OUT_SW_mirror: Dict[str, Dict] = {}
        # self.DB_mirror:
        # {
        # <label> :{
        #     "db_name": <db_name>,           # ns=3;s="conf"
        #     "values": {
        #         "label1": value1,           # label => "tWatchdog"
        #         }
        #     }
        # }
        self.DB_mirror: Dict[str, Dict] = {}
        # Per-instance IO mutex — serialises concurrent hardware operations.
        self._io_lock = threading.RLock()
        self._lock_timeout_seconds: float = 0.4
        # Set True during start()/stop() internals to bypass lock/retry logic.
        self._in_lifecycle: bool = False
        # Nesting depth for _with_retry; shared across the MRO via instance attribute.
        self._retry_depth: int = 0
        # Session-invalid auto-retry configuration (disabled by default).
        self._retry_on_session_invalid: bool = False
        self._retry_attempts: int = 3
        self._retry_delay: float = 0.01
        self._retry_markers: tuple = _DEFAULT_SESSION_MARKERS
        self._reconnect_callback: Optional[Callable[[], bool]] = None
        self._reconnecting: bool = False
        # Async recovery event log.
        self._recovery_log_path: Optional[Path] = None
        self._recovery_log_prefix: str = ""

        # E.g.:
        # self.IN_SW_mirror = {
        #     "K4331": {
        #         "nodeid": 'ns=3;s="K4331_IN_SW".Array',       # NodeId for the input array
        #         "value": [0, 0, 0, ..., 0],                   # Current value of the input array
        #         "value_type": list                            # Type of the value (list for arrays)
        #     },
        #     ...
        # }
        # self.OUT_SW_mirror = {
        #     "K4331": {
        #         "nodeid": 'ns=3;s="K4331_OUT_SW".Array',      # NodeId for the output array
        #         "value": [0, 0, 0, ..., 0],                   # Current value of the output array
        #         "value_type": list                            # Type of the value (list for arrays)
        #     },
        #     ...
        # }
        #
        # Sync or auto_io operations will update these mirrors accordingly, by reading from or writing to the OPC-UA server.
        # start() => the mirrors are initialized by reading the current state from the server.
        # read() => (update mirror if auto_io, then) reads from OUT_SW_mirror 
        # write() => writes to IN_SW_mirror (and if auto_io writes to server)
        # syncAll() => reads both IN_SW and OUT_SW from server to update mirrors
        # syncInputs() => reads IN_SW from server to update IN_SW_mirror
        # syncOutputs() => reads OUT_SW from server to update OUT_SW_mirror
        # readArrayIndex() => reads from OUT_SW_mirror at the specified index, updating from server if auto_io
        # writeArrayIndex() => modifies IN_SW_mirror at the specified index, writing to server if auto_io
        # setIN_SW() => configures an entry in IN_SW_mirror, read from server at start()
        # setOUT_SW() => configures an entry in OUT_SW_mirror, read from server at start()
        

     # region Debug handling
    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages with timestamp."""
        timestamp = timestamp or datetime.now().isoformat(timespec='milliseconds')
        if self.debug_enabled:
            print(f"{timestamp} - GPIO_Lib: {msg}")

    def setDebugFunction(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function

    # region Configuration API
    def setLockTimeout(self, seconds: float) -> None:
        """Set timeout for acquiring the per-device IO mutex."""
        self._lock_timeout_seconds = max(0.0, float(seconds))

    def setRetryAttempts(self, n: int) -> None:
        """Number of times to retry after a recoverable session error (default 3)."""
        self._retry_attempts = max(0, int(n))

    def setRetryDelay(self, seconds: float) -> None:
        """Seconds to wait between reconnect attempt and retry (default 0.01)."""
        self._retry_delay = max(0.0, float(seconds))

    def setRetryOnSessionInvalid(self, enabled: bool) -> None:
        """Enable or disable automatic retry on session-invalid OPC UA errors."""
        self._retry_on_session_invalid = bool(enabled)

    def setRetryMarkers(self, markers: list) -> None:
        """Substrings checked against str(exc) and type(exc).__name__ to identify
        retriable session-invalid errors. Replaces the default list.
        """
        self._retry_markers = tuple(markers)

    def setReconnectCallback(self, callback: Callable[[], bool]) -> None:
        """Callable invoked before each retry attempt. Must return True on success.
        If not set, a bare stop() + start() cycle is used instead.
        """
        self._reconnect_callback = callback

    def setRecoveryLogFile(self, path: str, prefix: str = "") -> None:
        """Append recovery events to *path*. Format: <ISO-ts> [prefix] <event>"""
        self._recovery_log_path = Path(path)
        self._recovery_log_prefix = prefix

    # region Internal retry / lock helpers
    def _is_retriable(self, exc: Exception) -> bool:
        """Return True if *exc* looks like an OPC UA session-invalid error."""
        if not self._retry_on_session_invalid:
            return False
        text = str(exc)
        name = type(exc).__name__
        return any(m in text or m == name for m in self._retry_markers)

    def _trace_recovery(self, event: str) -> None:
        """Append a timestamped recovery event to the configured log file
        without blocking the caller (written on a daemon thread).
        """
        if self._recovery_log_path is None:
            return
        path = self._recovery_log_path
        prefix = self._recovery_log_prefix

        def _write() -> None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().isoformat(timespec="milliseconds")
                parts = [ts, prefix, event] if prefix else [ts, event]
                with path.open("a", encoding="utf8") as fh:
                    fh.write(" ".join(parts) + "\n")
            except Exception:
                pass

        try:
            threading.Thread(target=_write, daemon=True).start()
        except Exception:
            pass

    def _do_reconnect(self) -> bool:
        """Stop the transport, invoke the reconnect callback (or bare stop+start),
        and trace the outcome. Sets _reconnecting=True for the duration so nested
        IO calls do not trigger further retries.
        """
        self._trace_recovery("recover_start")
        self._reconnecting = True
        ok = False
        failure_reason = "unknown"
        try:
            if self._reconnect_callback is not None:
                ok = bool(self._reconnect_callback())
                if not ok:
                    failure_reason = "callback_false"
            else:
                try:
                    self.stop()
                except Exception:
                    pass
                ok = bool(self.start())
                if not ok:
                    failure_reason = "start_false"
        except Exception as exc:
            name = type(exc).__name__
            failure_reason = f"exception_{name}"
            self._trace_recovery(f"recover_exception {name}")
            ok = False
        finally:
            self._reconnecting = False
        if ok:
            self._trace_recovery("recover_success")
        else:
            self._trace_recovery(f"recover_failed {failure_reason}")
        return ok

    def _with_retry(self, op: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *op* once; on a retriable exception attempt reconnect and retry
        up to _retry_attempts times. Re-raises the last exception when all attempts
        are exhausted or the error is not retriable.

        When _in_lifecycle is True (during start()/stop() internals), *op* is
        called directly without lock acquisition or retry.
        """
        if self._in_lifecycle:
            return op(*args, **kwargs)

        top_level = self._retry_depth == 0
        self._retry_depth += 1
        lock_acquired = False
        lock_timeout = self._lock_timeout_seconds
        try:
            if top_level:
                lock_acquired = self._io_lock.acquire(timeout=lock_timeout)
                if not lock_acquired:
                    self._trace_recovery("lock_timeout")
                    raise TimeoutError(
                        f"GPIO_Lib_OPCUA IO lock timeout after {lock_timeout:.2f}s"
                    )
            return op(*args, **kwargs)
        except Exception as first_exc:
            if (
                not top_level
                or not self._is_retriable(first_exc)
                or self._retry_attempts < 1
                or self._reconnecting
            ):
                raise
            last_exc = first_exc
            for _ in range(self._retry_attempts):
                if not self._do_reconnect():
                    raise last_exc
                if self._retry_delay > 0:
                    time.sleep(self._retry_delay)
                try:
                    return op(*args, **kwargs)
                except Exception as retry_exc:
                    last_exc = retry_exc
                    if not self._is_retriable(retry_exc):
                        raise
            raise last_exc
        finally:
            if top_level and lock_acquired:
                self._io_lock.release()
            self._retry_depth = max(0, self._retry_depth - 1)

    def setConfig(self, transport_config: OPCUATransportConfig) -> None:
        """Set the transport configuration."""
        self._transport_config = transport_config


    # region Legacy connect/disconnect
    def connect(self) -> bool:
        """Legacy connect() method; use start() instead."""
        print("connect() called (legacy); starting GPIO_Lib...")
        return self.start()

    def disconnect(self) -> None:
        """Legacy disconnect() method; use stop() instead."""
        print("disconnect() called (legacy); stopping GPIO_Lib...")
        self.stop()


# region SW mirror configuration
    def setIN_SW(self, label: str, nodeid: str, value_type: Any) -> None:
        """Configure a GPIO input.
        Arguments:
          - `label`: logical label for the GPIO input
          - `nodeid`: OPC-UA node ID for the input
          - `value_type`: initial value type hint
        """
        if not label:
            raise ValueError("setIN_SW called with empty label")
        if not nodeid:
            raise ValueError("setIN_SW called with empty nodeid")
        if not value_type:
            raise ValueError("setIN_SW called with empty value_type")
        if not isinstance(value_type, type):
            raise ValueError("setIN_SW called with invalid value_type; must be a type")
        if self._running:
            raise RuntimeError("Cannot add inputs after GPIO_Lib_OPCUA has started")

        self.IN_SW_mirror[label] = {
            "nodeid": nodeid,
            "value": value_type(),
            "value_type": value_type
        }

    def setOUT_SW(self, label: str, nodeid: str, value_type: Any) -> None:
        """Configure a GPIO output.
        Arguments:
          - `label`: logical label for the GPIO output
          - `nodeid`: OPC-UA node ID for the output
          - `value_type`: initial value type hint
        """
        if not label:
            raise ValueError("setOUT_SW called with empty label")
        if not nodeid:
            raise ValueError("setOUT_SW called with empty nodeid")
        if not value_type:
            raise ValueError("setOUT_SW called with empty value_type")
        if not isinstance(value_type, type):
            raise ValueError("setOUT_SW called with invalid value_type; must be a type")
        if self._running:
            raise RuntimeError("Cannot add outputs after GPIO_Lib_OPCUA has started")
        
        self.OUT_SW_mirror[label] = {
            "nodeid": nodeid,
            "value": value_type(),
            "value_type": value_type
        }


    def setDB(self, label: str, db_name: str, values: list[str]) -> None:
        """Configure a GPIO DB entry (maps to both IN_SW and OUT_SW).
        Arguments:
          - `label`: logical label for the GPIO
          - `db_name`: OPC-UA DB name for the entry (must be the same for IN_SW and OUT_SW)
          - `values`: list of initial values for the DB entry (used as type hint)
        """

        if not label:
            raise ValueError("setDB called with empty label")
        if not db_name:
            raise ValueError("setDB called with empty db_name")
        if not values:
            raise ValueError("setDB called with empty values list")
        if self._running:
            raise RuntimeError("Cannot add DB entries after GPIO_Lib_OPCUA has started")

        self.DB_mirror[label] = {
            "db_name": db_name,
            "values": values,
        }


    

    # region Start/Stop
    def start(self) -> bool:
        with self._io_lock:
            if self._running:
                raise RuntimeError("GPIO_Lib_OPCUA.start called when already running")

            if not self._transport_config:
                raise RuntimeError("GPIO_Lib_OPCUA.start called without transport_config configured")

            self._in_lifecycle = True
            try:
                # Prefer using the config factory so tests can inject a fake transport
                if hasattr(self._transport_config, "create_transport"):
                    self._transport = self._transport_config.create_transport()
                else:
                    self._transport = OPCUATransport(config=self._transport_config)
                self._transport.connect()
                self._running = True
                if not self._transport.is_connected:
                    self._running = False
                    self._transport = None
                    raise RuntimeError("GPIO_Lib_OPCUA.start failed to connect transport")

                # Fetch data from server to initialise mirrors.
                # On failure: clean up so the instance is not left in a half-started state.
                try:
                    self.syncAll(from_server=True)
                except Exception as sync_exc:
                    self._running = False
                    try:
                        self._transport.disconnect()
                    except Exception:
                        pass
                    self._transport = None
                    raise RuntimeError(
                        f"GPIO_Lib_OPCUA.start: syncAll failed during startup: {sync_exc}"
                    ) from sync_exc

                self.log_debug_message("### GPIO_Lib_OPCUA started successfully ####")
                return True
            finally:
                self._in_lifecycle = False

    def stop(self) -> None:
        with self._io_lock:
            if not self._running:
                raise RuntimeError("GPIO_Lib_OPCUA.stop called when not running")

            self.log_debug_message("Stopping GPIO_Lib_OPCUA")
            self._in_lifecycle = True
            try:
                if self._transport:
                    try:
                        self._transport.disconnect()
                    except Exception as e:
                        self.log_debug_message(f"Error while disconnecting transport: {e}")
            finally:
                self._running = False
                self._transport = None
                self._in_lifecycle = False


    # region Labels to Nodeid
    def _getNodeIdFromLabel(self, label: str, is_input: bool) -> Optional[str]:
        """Helper to get node ID from label."""
        collection = self.IN_SW_mirror if is_input else self.OUT_SW_mirror
        entry = collection.get(label)
        if entry:
            return entry["nodeid"]
        return None


    # region Read/Write GPIO
    def read(self, label: str, force: bool = False) -> Any:
        """
        Read OUT_SW value for the given label.
        Arguments:
            - `label`: logical label for the GPIO (reads OUT_SW)
            - `force`: if True, force read from transport even if auto_io is disabled
        Returns:
            - value read from the GPIO output (OUT_SW)
        """
        return self._with_retry(self._read_inner, label, force=force)

    def _read_inner(self, label: str, force: bool = False) -> Any:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.read called when not running")

        # Read from the configured OUTPUT node (OUT_SW)
        nodeid = self._getNodeIdFromLabel(label, is_input=False)
        if not nodeid:
            raise ValueError(f"GPIO_Lib_OPCUA.read: unknown output label '{label}'")

        if not self._transport_config.auto_io and not force:
            value = self.OUT_SW_mirror[label]["value"]
            self.log_debug_message(f"Read GPIO output '{label}' (nodeid={nodeid}) from cache: {value}")
            return value

        value = self._transport.read(nodeid)
        self.OUT_SW_mirror[label]["value"] = value
        self.log_debug_message(f"Read GPIO output '{label}' (nodeid={nodeid}): {value}")
        return value

    def write(self, label: str, value: Any, force: bool = False) -> None:
        """Write to the GPIO's input node (IN_SW) for the given label.
        Writing changes the desired hardware function; reading of the output
        node (OUT_SW) reflects the resulting status and is used to compute
        per-pin OK/fault state.
        Arguments:
            - `label`: logical label for the GPIO
            - `value`: value to write to the GPIO input (IN_SW)
            - `force`: if True, force write to transport even if auto_io is disabled
        """
        self._with_retry(self._write_inner, label, value, force=force)

    def _write_inner(self, label: str, value: Any, force: bool = False) -> None:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.write called when not running")

        nodeid_in = self._getNodeIdFromLabel(label, is_input=True)
        if not nodeid_in:
            raise ValueError(f"GPIO_Lib_OPCUA.write: unknown input label '{label}'")

        if not self._transport_config.auto_io and not force:
            # only update the IN cache; do not touch the server
            self.IN_SW_mirror[label]["value"] = value
            self.log_debug_message(f"Set GPIO input '{label}' (nodeid={nodeid_in}) in cache: {value}")
            return

        # write to IN_SW
        self._transport.write(nodeid_in, value)
        self.IN_SW_mirror[label]["value"] = value
        self.log_debug_message(f"Wrote GPIO input '{label}' (nodeid={nodeid_in}): {value}")
        # update outputs cache by reading OUT_SW when auto_io enabled
        nodeid_out = self._getNodeIdFromLabel(label, is_input=False)
        if nodeid_out:
            try:
                out_val = self._transport.read(nodeid_out)
                self.OUT_SW_mirror[label]["value"] = out_val
                self.log_debug_message(f"Updated output cache for '{label}' from node {nodeid_out}: {out_val}")
            except Exception:
                # If we cannot read the OUT node, leave it as-is and continue
                pass

    # region Read/Write with Array (Set index only)
    def readArrayIndex(self, label: str, index: int, force: bool = False) -> Any:
        """Read a GPIO input array element by label and index.
        Arguments:
          - `label`: logical label for the GPIO input
          - `index`: index into the array to read
          - `force`: if True, force read from transport even if auto_io is disabled
        """
        return self._with_retry(self._readArrayIndex_inner, label, index, force=force)

    def _readArrayIndex_inner(self, label: str, index: int, force: bool = False) -> Any:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.readArrayIndex called when not running")

        array_value = self.read(label, force=force)
        if not isinstance(array_value, (list, tuple)):
            raise ValueError(f"GPIO_Lib_OPCUA.readArrayIndex: GPIO input '{label}' is not an array")
        if index < 0 or index >= len(array_value):
            raise IndexError(f"GPIO_Lib_OPCUA.readArrayIndex: index {index} out of range for GPIO input '{label}'")
        value = array_value[index]
        self.log_debug_message(f"Read GPIO input array '{label}' index {index}: {value}")
        return value

    def writeArrayIndex(self, label: str, index: int, value: Any, force: bool = False) -> None:
        """Write a GPIO input array element by label and index (writes to IN_SW).
        Arguments:
          - `label`: logical label for the GPIO
          - `index`: index into the array to write
          - `value`: value to write at the specified index
          - `force`: if True, force write to transport even if auto_io is disabled
        """
        self._with_retry(self._writeArrayIndex_inner, label, index, value, force=force)

    def _writeArrayIndex_inner(self, label: str, index: int, value: Any, force: bool = False) -> None:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.writeArrayIndex called when not running")

        # Read the current input array (IN_SW) to modify it
        nodeid_in = self._getNodeIdFromLabel(label, is_input=True)
        if not nodeid_in:
            raise ValueError(f"GPIO_Lib_OPCUA.writeArrayIndex: unknown input label '{label}'")
        self.log_debug_message(f"GPIO_Lib_OPCUA.writeArrayIndex: reading current array for label '{label}' from nodeid {nodeid_in}")
        array_value = self.IN_SW_mirror[label]["value"]
        if self._transport_config.auto_io or force:
            array_value = self._transport.read(nodeid_in)

        if not isinstance(array_value, list):
            raise ValueError(f"GPIO_Lib_OPCUA.writeArrayIndex: GPIO input '{label}' is not an array. It is of type {type(array_value)}")
        if index < 0 or index >= len(array_value):
            raise IndexError(f"GPIO_Lib_OPCUA.writeArrayIndex: index {index} out of range for GPIO input '{label}'")
        array_value[index] = value
        # write modified input array
        self.write(label, array_value, force=force)
        self.log_debug_message(f"Wrote GPIO input array '{label}' index {index}: {value}")

    def readDB(self, label: str, key: str) -> Any:
        """Read a GPIO DB entry value by label and key.
        Arguments:
          - `label`: configured label for the GPIO DB
          - `key`: key within the DB entry to read
        """
        return self._with_retry(self._readDB_inner, label, key)

    def _readDB_inner(self, label: str, key: str) -> Any:
        """Inner DB read executed under _with_retry."""
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.readDB called when not running")

        entry = self.DB_mirror.get(label)
        if not entry:
            raise ValueError(f"GPIO_Lib_OPCUA.readDB: unknown DB label '{label}'")

        db_name = entry["db_name"]
        values = entry["values"]

        if key not in values:
            raise ValueError(f"GPIO_Lib_OPCUA.readDB: unknown key '{key}' for DB label '{label}'")

        db_nodeid = self._build_db_nodeid(db_name, key)
        db_value = self._transport.read(db_nodeid)
        self.log_debug_message(f"Read GPIO DB '{label}' ({db_name}) key '{key}': {db_value}")
        return db_value

    def writeDB(self, label: str, key: str, value: Any) -> None:
        """Write a GPIO DB entry value by label and key.
        Arguments:
          - `label`: configured label for the GPIO DB
          - `key`: key within the DB entry to write
          - `value`: value to write
        """
        self._with_retry(self._writeDB_inner, label, key, value)

    def _writeDB_inner(self, label: str, key: str, value: Any) -> None:
        """Inner DB write executed under _with_retry."""
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.writeDB called when not running")

        entry = self.DB_mirror.get(label)
        if not entry:
            raise ValueError(f"GPIO_Lib_OPCUA.writeDB: unknown DB label '{label}'")

        db_name = entry["db_name"]
        values = entry["values"]

        if key not in values:
            raise ValueError(f"GPIO_Lib_OPCUA.writeDB: unknown key '{key}' for DB label '{label}'")

        db_nodeid = self._build_db_nodeid(db_name, key)
        self._transport.write(db_nodeid, value)
        self.log_debug_message(f"Wrote GPIO DB '{label}' ({db_name}) key '{key}': {value}")

    def _build_db_nodeid(self, db_name: str, key: str) -> str:
        """Build DB node id as <db_name>.<key> for OPC UA read/write operations."""
        # Build DB node id as <db_name>.<key> while supporting both:
        # - namespace-qualified db_name, e.g. ns=3;s="conf"
        # - plain string db_name, e.g. conf (legacy)
        key_name = str(key).strip().strip('"')
        db_name_text = str(db_name).strip()
        if ";s=" in db_name_text:
            ns_prefix, symbol = db_name_text.split(";s=", 1)
            symbol = symbol.strip().strip('"')
            return f'{ns_prefix};s="{symbol}"."{key_name}"'
        else:
            return f'"{db_name_text.strip("\"")}"."{key_name}"'

    
    # region sync IO
    # Separate functions because outputs could change inputs
    def syncIN_SW(self, from_server: bool = False) -> None:
        """Perform a full sync of all GPIO inputs (read IN_SW)."""
        self._with_retry(self._syncIN_SW_inner, from_server)

    def _syncIN_SW_inner(self, from_server: bool = False) -> None:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.syncInputs called when not running")

        # Skip if auto_io is enabled
        if self._transport_config.auto_io:
            return

        # Sync inputs (IN_SW)
        for label in self.IN_SW_mirror.keys():
            nodeid = self._getNodeIdFromLabel(label, is_input=True)
            if not nodeid:
                continue
            if from_server:
                try:
                    value = self._transport.read(nodeid)
                    self.IN_SW_mirror[label]["value"] = value
                    self.log_debug_message(f"Synced GPIO input '{label}' (nodeid={nodeid}) from server: {value}")
                except Exception:
                    self.log_debug_message(f"Failed to read input node for '{label}' (nodeid={nodeid})")
                continue
            else:
                try:
                    value = self.IN_SW_mirror[label]["value"]
                    self._transport.write(nodeid, value)
                    self.log_debug_message(f"Synced GPIO input '{label}' (nodeid={nodeid}): {value}")
                except Exception:
                    self.log_debug_message(f"Failed to write input node for '{label}' (nodeid={nodeid})")

    def syncOUT_SW(self) -> None:
        """Perform a full sync of all GPIO outputs (read OUT_SW)."""
        self._with_retry(self._syncOUT_SW_inner)

    def _syncOUT_SW_inner(self) -> None:
        if not self._running or not self._transport:
            raise RuntimeError("GPIO_Lib_OPCUA.syncOutputs called when not running")

        # Skip if auto_io is enabled
        if self._transport_config.auto_io:
            return

        # Sync outputs (OUT_SW)
        for label in self.OUT_SW_mirror.keys():
            nodeid = self._getNodeIdFromLabel(label, is_input=False)
            if not nodeid:
                continue
            try:
                value = self._transport.read(nodeid)
                self.OUT_SW_mirror[label]["value"] = value
                self.log_debug_message(f"Synced GPIO output '{label}' (nodeid={nodeid}): {value}")
            except Exception:
                self.log_debug_message(f"Failed to read output node for '{label}' (nodeid={nodeid})")

    def syncAll(self, from_server: bool = False) -> None:
        """Perform a full sync of all GPIO inputs and outputs."""
        self.syncIN_SW(from_server=from_server)
        self.syncOUT_SW()
