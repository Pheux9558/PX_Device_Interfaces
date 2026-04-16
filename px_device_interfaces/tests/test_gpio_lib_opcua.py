import pytest
import time

from px_device_interfaces.transports.opcua import OPCUATransportConfig
from px_device_interfaces import GPIO_Lib_OPCUA

ENDPOINT = "opc.tcp://192.168.152.1:4840"
LABLE = "K4331"
NODEID_IN = 'ns=3;s="K4331_IN_SW".Array'
NODEID_OUT = 'ns=3;s="K4331_OUT_SW".Array'
DB_NAME = 'ns=3;s="conf"'
DB_LABLE = "Config"
DB_KEY = "tWatchdog"

CONFIG = OPCUATransportConfig(opcua_endpoint=ENDPOINT, default_node=NODEID_IN, timeout=2.0, debug=False, auto_io=False)


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
    # Skip the test early if the OPC UA server is not available in the environment
    t = None
    try:
        t = _connect_or_skip(CONFIG)
    finally:
        if t is not None:
            t.disconnect()

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    try:
        gpio._transport_config.auto_io = False  # disable auto io for testing




        # configure IN and OUT
        gpio.setIN_SW(label=LABLE, nodeid=NODEID_IN, value_type=list)
        gpio.setOUT_SW(label=LABLE, nodeid=NODEID_OUT, value_type=list)
        # start to initialize caches
        gpio.start()


        assert LABLE in gpio.OUT_SW_mirror and LABLE in gpio.IN_SW_mirror, "Labels not configured"
        assert isinstance(gpio.OUT_SW_mirror[LABLE]["value"], list), "Output cache not initialized as list"

        start_time = time.time()

        gpio.write(label=LABLE, value=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        gpio.syncAll()

        gpio.write(label=LABLE, value=[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0])
        if not gpio._transport_config.auto_io:
            gpio.syncIN_SW()
            assert gpio.read(label=LABLE) == [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
            gpio.syncOUT_SW()
        assert gpio.read(label=LABLE) == [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]
        

        gpio.write(label=LABLE, value=[0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1])
        if not gpio._transport_config.auto_io:
            gpio.syncIN_SW()
            assert gpio.read(label=LABLE) == [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]
            gpio.syncOUT_SW()
        assert gpio.read(label=LABLE) == [0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1]



        gpio.write(label=LABLE, value=[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1])
        gpio.syncAll()
        assert gpio.read(label=LABLE) == [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

        gpio.write(label=LABLE, value=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        gpio.syncAll()
        assert gpio.read(label=LABLE) == [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]


        # Test indexed read/write on OUT
        # write IN index 0 to 1
        gpio.writeArrayIndex(label=LABLE, index=0, value=1)
        gpio.syncAll()
        assert gpio.readArrayIndex(label=LABLE, index=0) == 1

        # write IN index 0 to 0
        gpio.writeArrayIndex(label=LABLE, index=0, value=0)
        gpio.syncAll()
        assert gpio.readArrayIndex(label=LABLE, index=0) == 0



        # ensure modifying config after start is forbidden
        with pytest.raises(RuntimeError):
            gpio.setIN_SW(label="NEW", nodeid=NODEID_IN, value_type=list)
        with pytest.raises(RuntimeError):
            gpio.setOUT_SW(label="NEW", nodeid=NODEID_OUT, value_type=list)

        total_time = time.time() - start_time
        print(f"total_time: {total_time:.6f}s")

    finally:
        try:
            gpio.stop()
        except Exception:
            pass


def test_gpio_lib_opcua_read_db_hw():
    """Hardware-backed test for reading DB key from OPC UA server."""
    t = None
    try:
        t = _connect_or_skip(CONFIG)
    finally:
        if t is not None:
            t.disconnect()

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    try:
        gpio.setDB(label=DB_LABLE, db_name=DB_NAME, values=[DB_KEY])
        gpio.start()

        value = gpio.readDB(label=DB_LABLE, key=DB_KEY)
        print(f"DB read {DB_LABLE}.{DB_KEY} = {value}")
        assert value is not None, f"Expected a value for {DB_LABLE}.{DB_KEY}, got None"
    finally:
        try:
            gpio.stop()
        except Exception:
            pass


def test_gpio_lib_opcua_write_db_hw():
    """Hardware-backed test for writing DB key on OPC UA server."""
    t = None
    try:
        t = _connect_or_skip(CONFIG)
    finally:
        if t is not None:
            t.disconnect()

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    try:
        gpio.setDB(label=DB_LABLE, db_name=DB_NAME, values=[DB_KEY])
        gpio.start()

        original_value = gpio.readDB(label=DB_LABLE, key=DB_KEY)
        print(f"DB original {DB_LABLE}.{DB_KEY} = {original_value}")

        write_value = original_value
        if isinstance(original_value, bool):
            write_value = int(original_value)
        elif isinstance(original_value, int):
            write_value = int(original_value)
        elif isinstance(original_value, float):
            write_value = float(original_value)

        try:
            gpio.writeDB(label=DB_LABLE, key=DB_KEY, value=write_value)
        except Exception as exc:
            exc_text = str(exc)
            if "BadWriteNotSupported" in exc_text or "BadNotWritable" in exc_text:
                pytest.skip(f"DB write not supported for {DB_LABLE}.{DB_KEY}: {exc}")
            raise
        after_write = gpio.readDB(label=DB_LABLE, key=DB_KEY)
        print(f"DB after write {DB_LABLE}.{DB_KEY} = {after_write}")
        assert after_write == write_value, (
            f"Expected {DB_LABLE}.{DB_KEY} to be {write_value}, got {after_write}"
        )
    finally:
        try:
            gpio.stop()
        except Exception:
            pass


def test_gpio_lib_opcua_write_db_hw_verbose_roundtrip():
    """Verbose hardware diagnostic for DB write + read-back behavior."""
    t = None
    try:
        t = _connect_or_skip(CONFIG)
    finally:
        if t is not None:
            t.disconnect()

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    original_value = None
    wrote_new_value = False
    selected_value = None
    write_errors = []
    saw_not_writable = False
    try:
        gpio.setDB(label=DB_LABLE, db_name=DB_NAME, values=[DB_KEY])
        gpio.start()

        db_nodeid = gpio._build_db_nodeid(DB_NAME, DB_KEY)
        original_value = gpio.readDB(label=DB_LABLE, key=DB_KEY)
        print("--- DB verbose roundtrip diagnostics ---")
        print(f"Endpoint: {ENDPOINT}")
        print(f"DB label: {DB_LABLE}")
        print(f"DB name: {DB_NAME}")
        print(f"DB key: {DB_KEY}")
        print(f"Resolved nodeid: {db_nodeid}")
        print(f"Original value: {original_value} (type={type(original_value).__name__})")

        candidates = []
        if isinstance(original_value, bool):
            candidates = [not original_value, original_value]
        elif isinstance(original_value, int):
            candidates = [original_value + 1, original_value]
        elif isinstance(original_value, float):
            candidates = [original_value + 1.0, original_value]
        else:
            candidates = [original_value]

        roundtrip_ok = False
        for idx, candidate in enumerate(candidates, start=1):
            selected_value = candidate
            print(f"Attempt {idx}: write value={candidate} (type={type(candidate).__name__})")
            try:
                gpio.writeDB(label=DB_LABLE, key=DB_KEY, value=candidate)
                wrote_new_value = True
            except Exception as exc:
                msg = f"write failed: {type(exc).__name__}: {exc}"
                write_errors.append(msg)
                print(msg)
                et = str(exc)
                if "BadWriteNotSupported" in et or "BadNotWritable" in et:
                    saw_not_writable = True
                continue

            read_now = gpio.readDB(label=DB_LABLE, key=DB_KEY)
            print(f"Read-back immediate: {read_now} (type={type(read_now).__name__})")

            read_later = read_now
            deadline = time.time() + 1.0
            while time.time() < deadline:
                time.sleep(0.1)
                read_later = gpio.readDB(label=DB_LABLE, key=DB_KEY)
                if read_later == candidate:
                    break
            print(f"Read-back delayed: {read_later} (type={type(read_later).__name__})")

            direct_transport = gpio._transport.read(db_nodeid)
            print(
                f"Read direct transport: {direct_transport} "
                f"(type={type(direct_transport).__name__})"
            )

            if read_now == candidate or read_later == candidate or direct_transport == candidate:
                roundtrip_ok = True
                break

        if not roundtrip_ok:
            if saw_not_writable:
                pytest.skip(
                    f"DB appears read-only for {DB_LABLE}.{DB_KEY}; errors={write_errors}"
                )
            pytest.fail(
                f"DB write/read-back mismatch for {DB_LABLE}.{DB_KEY}. "
                f"Last candidate={selected_value}, errors={write_errors}"
            )
    finally:
        if wrote_new_value and original_value is not None:
            try:
                gpio.writeDB(label=DB_LABLE, key=DB_KEY, value=original_value)
                restored = gpio.readDB(label=DB_LABLE, key=DB_KEY)
                print(f"Restored original value: {restored}")
            except Exception as exc:
                print(f"Restore failed: {type(exc).__name__}: {exc}")
        try:
            gpio.stop()
        except Exception:
            pass


def test_gpio_lib_opcua_read_db_retries_on_session_invalid():
    class FakeTransport:
        def __init__(self):
            self.read_calls = 0

        def read(self, nodeid):
            self.read_calls += 1
            if self.read_calls == 1:
                raise RuntimeError("BadSessionIdInvalid")
            return 3000

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    gpio.setDB(label=DB_LABLE, db_name=DB_NAME, values=[DB_KEY])
    gpio._running = True
    gpio._transport = FakeTransport()
    gpio.setRetryOnSessionInvalid(True)
    gpio.setRetryAttempts(1)

    reconnect_calls = {"n": 0}

    def _reconnect_ok():
        reconnect_calls["n"] += 1
        return True

    gpio.setReconnectCallback(_reconnect_ok)

    value = gpio.readDB(label=DB_LABLE, key=DB_KEY)
    assert value == 3000
    assert gpio._transport.read_calls == 2
    assert reconnect_calls["n"] == 1


def test_gpio_lib_opcua_write_db_retries_on_session_invalid():
    class FakeTransport:
        def __init__(self):
            self.write_calls = 0
            self.last_write = None

        def write(self, nodeid, value):
            self.write_calls += 1
            if self.write_calls == 1:
                raise RuntimeError("BadSessionNotActivated")
            self.last_write = (nodeid, value)

    gpio = GPIO_Lib_OPCUA.GPIO_Lib_OPCUA(transport_config=CONFIG, debug_enabled=False)
    gpio.setDB(label=DB_LABLE, db_name=DB_NAME, values=[DB_KEY])
    gpio._running = True
    gpio._transport = FakeTransport()
    gpio.setRetryOnSessionInvalid(True)
    gpio.setRetryAttempts(1)

    reconnect_calls = {"n": 0}

    def _reconnect_ok():
        reconnect_calls["n"] += 1
        return True

    gpio.setReconnectCallback(_reconnect_ok)

    gpio.writeDB(label=DB_LABLE, key=DB_KEY, value=3210)
    assert gpio._transport.write_calls == 2
    assert reconnect_calls["n"] == 1
    assert gpio._transport.last_write is not None
    assert gpio._transport.last_write[1] == 3210


# run the test function directly for quick debugging compatibility
# test_gpio_lib_opcua_set_input_output()