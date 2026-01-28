# Transports

This package contains small, well-tested transport implementations used by
the connection layer. Transports encapsulate how bytes or messages are
sent to and received from devices (serial/USB, OPC UA, in-memory mock,
etc.). They are intentionally small and focused on testability so you can
implement and test transports without hardware.

---

## Overview

Key files:

- `base.py` — Defines `BaseTransport` and `BaseTransportConfig`. Subclasses
  implement connect/disconnect/send/receive/is_connected and may provide
  convenience helpers specific to the transport.
- `mock.py` — `MockTransport` and `MockTransportConfig`: an in-memory
  transport useful for unit tests and simulations.
- `usb.py` — `USBTransport` and `USBTransportConfig`: a pyserial-based
  serial/USB transport with helpers like `setTimeOut()` and `scan()`.
- `__init__.py` — Factory helpers (`get_transport_config_class()`, 
  `list_transport_types()`)

---

## Design & Best Practices

- Prefer configuration via dataclass configs (e.g. `USBTransportConfig`,
  `MockTransportConfig`). These expose required fields and provide a
  `create_transport()` factory method.
- `BaseTransport` exposes both `receive()` (text/backwards compatibility)
  and `receive_bytes()` (binary, preferred for framed protocols).
- Keep transports deterministic and minimal — use `MockTransport` for
  unit tests to avoid flaky hardware-dependent tests.
- Make debug output injectable using `setDebugFunction()` so test harnesses
  can capture logs.

---

## Examples

Creating a transport via a config dataclass and using it with `GPIO_Lib`:

```python
from px_device_interfaces.transports.usb import USBTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib

cfg = USBTransportConfig(port="COM7", baud=115200, timeout=0.1, debug=True)
gpio = GPIO_Lib(transport_config=cfg, auto_io=True, debug=True)
try:
    gpio.start()  # config creates + opens the transport
    gpio.pin_mode(13, "OUTPUT", name="LED13")
    gpio.digital_write("LED13", True)
finally:
    gpio.stop()
```

Using the `MockTransport` in tests:

```python
from px_device_interfaces.transports.mock import MockTransport, MockTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib

cfg = MockTransportConfig(loopback=True, debug=True, timeout=0.1)
gpio = GPIO_Lib(transport_config=cfg, auto_io=False, debug=True)
# In tests you can replace or inspect the transport instance
mock = MockTransport(loopback=True)
mock.connect()
gpio._transport = mock
# push/inspect bytes using mock._incoming, mock._sent, mock.pop_sent()
```


---

## Implementing a new transport

1. Create `your_transport.py` implementing a subclass of
   `BaseTransport` and an associated dataclass `YourTransportConfig`.
2. Implement `create_transport()` in the config dataclass to return an
   instance of the transport.
3. Add a small `scan()` classmethod to support discovery where applicable.
4. Add unit tests using `MockTransport` where possible and exercise
   connect/send/receive logic.
5. Add the new `TransportConfig` to `get_transport_config_class()`
   if you want ad-hoc lookups.

---

## Debugging tips

- Use `setDebugFunction()` on the transport or set `.debug = True` to
  enable timestamped debug messages.
- Prefer `receive_bytes()` for binary/framed protocols to avoid
  decode/fallback corruption (e.g. replacement characters).
- Use `MockTransport` to reproduce timing or sequence issues reliably and
  to exercise the queue/send-worker logic.

