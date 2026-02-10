# Copilot / AI Agent Instructions — PX_Device_Interfaces

Purpose
- This repository contains the Python host library in `px_device_interfaces/` and the MCU firmware in `firmware/GPIO_Lib_Firmware/`.

Quick architecture (what to read first)
- Host protocol & constants: [px_device_interfaces/GPIO_Lib.py](px_device_interfaces/GPIO_Lib.py) — framing helpers, `GPIO_Lib` class, and `CMD_` constants.
- Transports & mocks: [px_device_interfaces/transports/](px_device_interfaces/transports/) — `BaseTransport`, `MockTransport` (use for unit tests), and transport configs like `usb.py`.
- Examples & runtime: [px_device_interfaces/examples/](px_device_interfaces/examples/) — show repo-root `sys_files/GPIO_Lib/<device>.data` usage.
- Firmware: [firmware/GPIO_Lib_Firmware/src/](firmware/GPIO_Lib_Firmware/src/) and firmware libraries like [firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h](firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h).

Key conventions and patterns (project-specific)
- Packet framing: `CMD_START_BYTE` = `0xAA`. Packet layout is CMD (2 bytes), LEN (2 bytes), PAYLOAD, CHK. See `_build_packet()` / `_parse_frame()` in [px_device_interfaces/GPIO_Lib.py](px_device_interfaces/GPIO_Lib.py). Checksum: `(CMD + LEN + sum(PAYLOAD)) & 0xFF`.
- Command definitions: all `CMD_...` constants live in [px_device_interfaces/GPIO_Lib.py](px_device_interfaces/GPIO_Lib.py). When adding/removing commands, mirror the change in firmware headers (see [firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h](firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h)).
- I/O config files: repo-relative `sys_files/GPIO_Lib/<device>.data` (create if missing). Lines starting with `>` are directives parsed by `GPIO_Lib.configure_io()`; examples are in [px_device_interfaces/examples/blink_pin_configured.py](px_device_interfaces/examples/blink_pin_configured.py).
- Use `MockTransport` in [px_device_interfaces/transports/mock.py](px_device_interfaces/transports/mock.py) for unit tests to avoid hardware dependence.
- Settings persistence: per-device JSON settings live under `sys_files/Connection_Organiser/`.

Developer workflows (copy-paste)
- Install deps:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

- Run unit tests:

```bash
pytest -q
```

- Run a host example (from repo root):

```bash
python -m px_device_interfaces.examples.blink_pin_configured --pin 13
```

- Build/upload firmware (PlatformIO):

```bash
cd firmware/GPIO_Lib_Firmware
pio run
pio run -t upload --upload-port /dev/ttyACM0
```

Important integration notes
- External deps: `pyserial` and `opcua` are primary runtime dependencies; GUI demos use `tkinter`.
- Transport types: USB serial, TCP (WiFi), and OPC‑UA are implemented — see [px_device_interfaces/transports/](px_device_interfaces/transports/).
- Optional firmware features: the `FASTLED` module is controlled by the build flag `-DFASTLED`. Remove `-DFASTLED` (or use the `T-Dongle-S3-minimal` env) to exclude the FastLED module and save flash/RAM.

Guidance for AI agents working in this repo
- Always prefer changing APIs in the host package first and keep host and firmware command lists synchronized.
- Avoid touching legacy code paths unless requested; legacy textual protocols are for reference only.
- Small change rule: if you change a `CMD_` value, update the corresponding firmware handler (or add a compatibility shim) and run unit tests.
- Use `MockTransport` for tests and add unit tests under [px_device_interfaces/tests/](px_device_interfaces/tests/) when adding behavior.

Quick references (where to look for examples)
- Packet helpers and constants: [px_device_interfaces/GPIO_Lib.py](px_device_interfaces/GPIO_Lib.py)
- Transport implementations and mocks: [px_device_interfaces/transports/](px_device_interfaces/transports/)
- Firmware command helpers: [firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h](firmware/GPIO_Lib_Firmware/lib/cmd/src/cmd.h)
- Examples: [px_device_interfaces/examples/](px_device_interfaces/examples/)
- Tests: [px_device_interfaces/tests/](px_device_interfaces/tests/)

If anything here is unclear or you want the agent to expand a section (firmware snippets, migration steps, or runnable test harnesses), say which area to expand and I will update the file.
