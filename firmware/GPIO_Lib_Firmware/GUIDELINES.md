Firmware DESIGN and Architecture — GPIO_Lib_Firmware

# Edit to remove RTOS. Its not uesd and complicates things.
# Edit to add CMD references in each modules

Purpose
- Define structure, module rules, and design constraints to make firmware modular, testable, and portable across MCUs (ESP32, RP2040, STM32, nRF52, AVR).

Files / Folder structure
- `/src/main.cpp`: Main firmware loop and initialization. 
- `/lib/interfaces/`: Communication interface libraries (Serial, I2C, SPI, CAN). Provide class-style interfaces and factory registration.
- `/lib/peripherals/`: Peripheral drivers (GPIO, Servo, LCD, Sensor). Drivers accept interface references where applicable.
- `/lib/cmd/`: Central command packet framing/parsing. Hands off parsed commands to registered modules.
- `/lib/nvm/`: Non-volatile memory (EEPROM/Flash) helpers and configuration loader. If not defined, config defaults come from device driver defaults.

Build-time modularity
- Modules are included/excluded via `build_flags` in `platformio.ini` (e.g. `-DENABLE_LCD`, `-DENABLE_I2C`).
- On build, the user selects which modules to include by adding the corresponding build flags in CLI tool "scan_or_select.py".
- Each module must define its own build-flag constants and a small helper macro/func returning its flags and version string.

CMD_FIRMWARE_BUILD_FLAGS (0xFFFD) behavior
- When host requests build flags, the firmware must collect info from every compiled module.
- Each module exposes a short string (flags/version). The `cmd` subsystem queries modules in turn.
- The firmware builds a concatenated UTF-8 payload consisting of module entries and returns it using the standard framed response flow. Success is reported with `0x1000` (OK); failures send `0x1001` (ERROR).

Startup sequence (Setup)
1. `main.cpp` initializes core subsystems (serial console, minimal logging).
2. Initialize 'lib/cmd' to handle command framing/parsing.
3. Initialize 'lib/nvm' if enabled to load saved configuration, allowinf for basic functionality before host commands.
4. If no NVM, use compile-time defaults for module configuration.
5. Initialize selected communication interfaces and peripheral drivers according to loaded settings or compile-time defaults.
6. Emit a `READY` banner on the selected transport(s) to signal host availability.
7. Enter main loop for command processing.

Non-volatile memory rules
- `lib/nvm` provides a small, safe API to read/write configuration structures.
- On constrained MCUs avoid large dynamic allocations; use fixed-size records and checksums.
- Data is saved only on explicit host commands (e.g. `CMD_LCD_SAVE_SETTINGS`).
- Data is saved in packets the same way as host commands (CMD, LEN, PAYLOAD, CHK). That way, future-proofing and integrity checks are built-in and cmd parsing code can be reused.
- List of defalt storage devices to check (in order): EEPROM, internal Flash, external Flash (SPI/QSPI). If none are available, NVM is disabled. 

Run-time design (Loop)
- Main loop calls `cmd.process_incoming()` or similar to read/parse incoming bytes.
- `cmd.process_incoming()` or similar dispatches complete commands to module cmd handlers.

Command handling system
- Single framing/parsing implementation in `lib/cmd` matching host framing (START 0xAA, CMD(2), LEN(2), PAYLOAD, CHK).
- The dispatcher maps CMD ranges to module handlers. Each module registers handler(s) at init time.
- Handlers return standard status codes and may optionally emit asynchronous events.
- All outgoing packets must reuse a single transmit path provided by the selected interface abstraction.
- Handles Interface and Peripheral instances when the host creates them and tracks them by ID.
- Supports multiple instances of same interface/peripheral type.
- Peripherals can accept interface references for communication, by given the interface ID in the CMD payload. Setup commands for peripherals specify which interface type to use (and its ID).

Interfaces (communication)
- Each interface is a class implementing `init()`, `send(bytes)`, `receive(buf, timeout)`.
- Interfaces register with an ID so peripherals and modules can reference them.
- Multiple instances of same type are supported and selected by ID in CMD payloads.
- Host can create interfaces at runtime via CMDs (e.g. `CMD_I2C_CREATE`).

Peripherals
- Drivers are class-based and accept an interface reference where applicable.
- Drivers handle their own CMD subrange and implement init/config/read/write methods.
- Peripherals should avoid blocking long time in APIs; use queues/tasks for lengthy operations.
- Host can create peripherals at runtime via CMDs (e.g. `CMD_LCD_CREATE`).
- Each peripheral driver includes custom CMDs for configuration and operation (e.g. `CMD_LCD_WRITE_TEXT`).

Error codes & diagnostics
- Use `0x1000` for OK and `0x1001` for ERROR in packet-level responses.
- Include module/version entries in the build-flags response to aid host selection.
- Provide a `DEBUG` build flag enabling verbose logging over selected interface(s), same as gpio_lib comunication interface.

Testing & tooling
- Keep a `tools/` scanner (already present) to read `CMD_FIRMWARE_BUILD_FLAGS` for auto-configuring `platformio.ini`.


Notes
- Document each module's build-flag(s) and default config in a small `README.md` inside the module folder.
- Each module must implement a `module_flags()` function returning its build flags/version string for the build-flags aggregation command.

This document is the canonical short-form guideline for implementing modular firmware in this repository. For any module you add, follow these rules and include a one-line `module_flags()` function that returns the module's flags/version for the build-flags aggregation command.


# Upload Firmware with platformIO
To build and upload the firmware to a connected board, use PlatformIO commands:

Build firmware:
```bash
pio run
```

Upload firmware to connected board:
```bash
pio run -t upload  # upload to connected board
```
Port selection and build flag selection happens automatically.
extra_scripts will trigger the `scan_or_select.py` tool to help select the correct board and upload port if needed.
In addition if the script cant find a allready configured board it will prompt the user to select one from a list of detected boards, select the platform and build flags to use. The script will then update the platformio.ini file with the selected options and compile/upload the firmware.
