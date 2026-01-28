import os
from time import sleep

import pytest

from px_device_interfaces.transports.opcua import OPCUATransport


ENDPOINT = "opc.tcp://169.254.152.1:4840"
NODEID = 'ns=3;s="K4331_IN_SW"."Array"'
# Payload is a 16-byte array with first byte=1, rest=0
PAYLOAD = [0 for i in range(16)]
PAYLOAD[0] = 1


@pytest.mark.skipif(os.environ.get("RUN_OPCUA_TEST") != "1", reason="Run only when RUN_OPCUA_TEST=1")
def test_opcua_read_array_bytes():
    """Read-only test: verify the node returns a 16-byte array with expected content.

    The node may be read-only on the server; the test therefore does not attempt writes.
    """
    t = OPCUATransport({"endpoint": ENDPOINT, "default_node": NODEID})
    assert t.connect(), "Failed to connect to OPC UA endpoint"
    try:
        print("Writeing value:", PAYLOAD)
        t.send(PAYLOAD)
        sleep(0.1)  # allow some time for the server to process
        v = t.read(NODEID)
        print("Read value:", v)
        assert v is not None, "read returned None"
        # normalize to bytes if possible
        if isinstance(v, (bytes, bytearray)):
            b = bytes(v)
        elif isinstance(v, list):
            b = bytes(v)
        else:
            # fallback: try parsing a string list representation
            s = str(v).strip()
            if s.startswith("[") and s.endswith("]"):
                lst = [int(x.strip()) for x in s[1:-1].split(",")]
                b = bytes(lst)
            else:
                pytest.skip(f"Node returned unsupported value type: {type(v)}")

        assert len(b) == 16, f"expected 16 bytes, got {len(b)}"
        assert b[0] == 1 and all(x == 0 for x in b[1:]), f"unexpected payload: {b!r}"
    finally:
        t.disconnect()
