# Copilot / AI Agent Instructions — PX_Device_Interfaces

Purpose
- PX_Device_Interfaces contains the Python host libraries and the device firmware for PX hardware. Host code is in `python/`; main firmware is in `firmware/GPIO_Lib_Firmware/`.

Quick architecture (what to read first)
- Host binary protocol: `python/GPIO_Lib.py` — framing helpers, command constants, and the `GPIO_Lib` class (reads `sys_files/GPIO_Lib/<device>.data`).
- Transport layer: `python/transports/` — `BaseTransport`, `MockTransport`, and the factory `create_transport_for_device()`.
- Settings/persistence: `python/settings_manager.py` and `python/sys_files/` — per-device JSON settings under `sys_files/Connection_Organiser/`.
- Firmware: `firmware/GPIO_Lib_Firmware/src/` and `platformio.ini` — PlatformIO project implementing the same command IDs.

Key conventions you must follow
- I/O config files: lines starting with `>` in `sys_files/GPIO_Lib/<name>.data` are parsed by `GPIO_Lib.configure_io()` as `>use pin name` (examples: `>input_digital 15 S15`, `>lcd 20:4 LCD`). Other lines are ignored. This will be refactored soon to a pinMode() or similar API.
- Command IDs: defined as `CMD_` constants in `python/GPIO_Lib.py` and `firmware/GPIO_Lib_Firmware/src/commands.h`.
- Protocol flavors: legacy textual M/P commands live in `python_old/` for reference; the modern framed binary protocol is implemented in `python/GPIO_Lib.py` (START_BYTE=0xAA, 2-byte CMD, 2-byte LEN, PAYLOAD, CHK).
- Settings: `load_connection_settings()`/`save_connection_settings()` in `python/settings_manager.py` manage per-device JSON files in `sys_files/Connection_Organiser/`.

Developer workflows (copy-paste)
- Install deps:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional
```
- Run tests:
```bash
pytest -q
```
- Run an example:
```bash
python3 python/examples/blink_led13.py
```
# Copilot / AI Agent Instructions — PX_Device_Interfaces

Purpose
- This repo contains the Python host libraries (`python/`) and MCU firmware (`firmware/GPIO_Lib_Firmware/`) for PX devices. Host implements a framed binary protocol; firmware mirrors command IDs and behavior.

Quick architecture (read first)
- Host protocol & constants: [python/GPIO_Lib.py](python/GPIO_Lib.py)
- Transport layer & mocks: [python/transports/](python/transports/) — use [python/transports/mock.py](python/transports/mock.py) for tests
- Settings & per-device JSON: [python/settings_manager.py](python/settings_manager.py) and [python/sys_files/Connection_Organiser/](python/sys_files/Connection_Organiser/)
- Firmware sources & build: [firmware/GPIO_Lib_Firmware/src/](firmware/GPIO_Lib_Firmware/src/) and [firmware/GPIO_Lib_Firmware/platformio.ini](firmware/GPIO_Lib_Firmware/platformio.ini)

Critical conventions (do not change lightly)
- I/O config parsing: lines beginning with `>` in files under [python/sys_files/GPIO_Lib/](python/sys_files/GPIO_Lib/) are parsed by `GPIO_Lib.configure_io()` as directives (e.g. `>input_digital 15 S15`).
- Command identifiers: `CMD_` constants live in [python/GPIO_Lib.py](python/GPIO_Lib.py) and firmware headers — update both when changing IDs.
- Packet framing: START_BYTE = `0xAA`; layout is CMD (2B), LEN (2B), PAYLOAD, CHK. See `_build_packet()` / `_parse_frame()` in [python/GPIO_Lib.py](python/GPIO_Lib.py). Checksum formula: `(CMD + LEN + sum(PAYLOAD)) & 0xFF`.

Developer workflows (copy-paste)
- Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```
- Run tests:
```bash
pytest -q
```
- Run an example:
```bash
python3 python/examples/blink_led13.py
```
- Build/upload firmware:
```bash
cd firmware/GPIO_Lib_Firmware
pio run
pio run -t upload --upload-port /dev/ttyACM0
```
Use `tools/scan_and_select.py` to enumerate ports.

Integration notes
- Key packages: `pyserial`, `opcua`. GUI code uses `tkinter` (install `python3-tk` on Debian/Ubuntu).
- Transports: USB serial, TCP sockets (WIFI), OPC‑UA. Some tests need hardware or an OPC server.

Rules for AI agents working here
- Prioritize forward-facing API changes; do not maintain legacy shims unless requested. When changing protocol or CMDs, update host and firmware in tandem.
- Modify `python/transports/*` and `python/settings_manager.py` for connection-layer work. Document sys_files format changes in `TODO.md`.
- Use `MockTransport` for unit tests to avoid relying on hardware.

Quick references
- Packet helpers: `_build_packet()` and `_parse_frame()` in [python/GPIO_Lib.py](python/GPIO_Lib.py).
- I/O config parsing: `GPIO_Lib.configure_io()` (reads [python/sys_files/GPIO_Lib/](python/sys_files/GPIO_Lib/) files).
- Tests: look at `python/tools/test_gpio_mock.py` and other tests in `python/tools/` for examples.

Files to inspect first
- [python/GPIO_Lib.py](python/GPIO_Lib.py)
- [python/transports/](python/transports/)
- [python/settings_manager.py](python/settings_manager.py) and [python/sys_files/](python/sys_files/)
- [firmware/GPIO_Lib_Firmware/src/](firmware/GPIO_Lib_Firmware/src/)
- [python/examples/](python/examples/) and [firmware/tools/](firmware/tools/)

If you want expansion (firmware snippets, migration scripts, or runnable test harnesses), tell me which section to expand and I will add concrete examples.
