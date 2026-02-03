import pytest
import time

from px_device_interfaces.transports.opcua import OPCUATransportConfig
from px_device_interfaces import GPIO_Lib_OPCUA

ENDPOINT = "opc.tcp://169.254.152.1:4840"
LABLE = "K4331"
NODEID_IN = 'ns=3;s="K4331_IN_SW".Array'
NODEID_OUT = 'ns=3;s="K4331_OUT_SW".Array'

CONFIG = OPCUATransportConfig(opcua_endpoint=ENDPOINT, default_node=NODEID_IN, timeout=2.0, debug=True, auto_io=True)


def _connect_or_skip(cfg: OPCUATransportConfig):
    t = cfg.create_transport()
    ok = t.connect()
    if not ok or not t.is_connected:
        pytest.skip("OPC UA server not available at {}".format(cfg.opcua_endpoint))
    return t

def test_opcua_skip_if_unavailable():
    t = _connect_or_skip(CONFIG)
    t.disconnect()

def test_opcua_transport_connection():
    t = _connect_or_skip(CONFIG)
    try:
        assert t.is_connected, "OPC UA transport failed to connect"
    finally:
        t.disconnect()
        assert not t.is_connected, "OPC UA transport failed to disconnect"


def test_opcua_transport_read_write():
    t = _connect_or_skip(CONFIG)
    try:
        assert t.is_connected, "OPC UA transport failed to connect"

        # Write a test payload
        test_payload = [0 for i in range(16)]
        test_payload[0] = 1
        t.write(NODEID_IN, test_payload)

        # Poll for the value to appear at the output node, giving server a bit of time
        read_value = None
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                read_value = t.read(NODEID_OUT)
            except Exception:
                read_value = None
            if read_value:
                # normalize bytearray/bytes/list to indexable sequence of ints
                if isinstance(read_value, (bytes, bytearray)):
                    if len(read_value) > 0:
                        break
                elif isinstance(read_value, list) and len(read_value) > 0:
                    break
            time.sleep(0.005)

        assert read_value is not None, "No value read from output node"
        # extract first element robustly
        first = None
        if isinstance(read_value, (bytes, bytearray)):
            first = read_value[0]
        elif isinstance(read_value, list):
            first = read_value[0]
        else:
            # try to coerce
            try:
                first = int(read_value[0])
            except Exception:
                pytest.fail(f"Could not interpret read value: {read_value}")

        assert first == 1, f"OPC UA transport read value mismatch: expected 1, got {first}"

        # reset the output node
        test_payload[0] = 0
        t.write(NODEID_IN, test_payload)


    finally:
        t.disconnect()
        assert not t.is_connected, "OPC UA transport failed to disconnect"


def test_gpio_lib_opcua_set_input_output():
    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=True)
    try:
        # check auto_io. Need to be true to work in this test
        assert gpio._transport_config.auto_io, "GPIO_Lib_OPCUA transport_config.auto_io must be True for this test"



        # configure IN and OUT
        gpio.setIN_SW(label=LABLE, nodeid=NODEID_IN, value_type=list)
        gpio.setOUT_SW(label=LABLE, nodeid=NODEID_OUT, value_type=list)
        # start to initialize caches
        gpio.start()


        assert LABLE in gpio.OUT_SW_mirror and LABLE in gpio.IN_SW_mirror, "Labels not configured"
        assert isinstance(gpio.OUT_SW_mirror[LABLE]["value"], list), "Output cache not initialized as list"

        # initial OUT should be zeros (per FakeTransport)
        assert gpio.OUT_SW_mirror[LABLE]["value"][0] == 0

        # write IN index 0 to 1
        gpio.writeArrayIndex(label=LABLE, index=0, value=1)
        assert gpio.OUT_SW_mirror[LABLE]["value"][0] == 1

        # write IN index 0 to 0
        gpio.writeArrayIndex(label=LABLE, index=0, value=0)
        assert gpio.OUT_SW_mirror[LABLE]["value"][0] == 0



        # ensure modifying config after start is forbidden
        with pytest.raises(RuntimeError):
            gpio.setIN_SW(label="NEW", nodeid=NODEID_IN, value_type=list)
        with pytest.raises(RuntimeError):
            gpio.setOUT_SW(label="NEW", nodeid=NODEID_OUT, value_type=list)

    finally:
        try:
            gpio.stop()
        except Exception:
            pass


# run the test function directly for quick debugging compatibility
# test_gpio_lib_opcua_set_input_output()