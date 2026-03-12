

from datetime import datetime
from typing import Any, Dict, Optional
from px_device_interfaces.transports.opcua import OPCUATransport, OPCUATransportConfig







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
    

    # region Start/Stop
    def start(self) -> bool:
        if self._running:
            raise RuntimeError("GPIO_Lib_OPCUA.start called when already running")

        if not self._transport_config:
            raise RuntimeError("GPIO_Lib_OPCUA.start called without transport_config configured")
        # Prefer using the config factory so tests can inject a fake transport
        if hasattr(self._transport_config, "create_transport"):
            self._transport = self._transport_config.create_transport()
        else:
            self._transport = OPCUATransport(config=self._transport_config)
        self._transport.connect()
        self._running = True
        if not self._transport.is_connected:
            self._running = False
            raise RuntimeError("GPIO_Lib_OPCUA.start failed to connect transport")

        # Fetch data from server to initialize inputs and outputs
        self.syncAll(from_server=True)

        

        # Code to start the GPIO_Lib_OPCUA functionality
        self.log_debug_message("### GPIO_Lib_OPCUA started successfully ####")

        return True

    def stop(self) -> None:
        if not self._running:
            raise RuntimeError("GPIO_Lib_OPCUA.stop called when not running")
        
        # Code to stop the GPIO_Lib_OPCUA functionality
        self.log_debug_message("Stopping GPIO_Lib_OPCUA")
        if self._transport:
            try:
                self._transport.disconnect()
            except Exception as e:
                self.log_debug_message(f"Error while disconnecting transport: {e}")
            finally:
                self._running = False
                self._transport = None


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


    
    # region sync IO
    # Seperate functions because outputs could change inputs
    def syncIN_SW(self, from_server = False) -> None:
        """Perform a full sync of all GPIO inputs (read IN_SW)."""
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

    def syncAll(self, from_server = False) -> None:
        """Perform a full sync of all GPIO inputs and outputs."""
        self.syncIN_SW(from_server=from_server)
        self.syncOUT_SW()
