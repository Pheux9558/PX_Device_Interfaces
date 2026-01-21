# TODO — PX_Device_Interfaces Rewrite

This file tracks the planned refactoring to separate transports, improve settings management, and create reusable device driver templates.

## Progress Legend
- [ ] Not started
- [x] Completed
- [~] In progress

---

## Tasks

### [x] Setup Python `.venv` 3.13.7 and dev deps
Add instructions and optional helper script to create a `.venv` using Python 3.13.7. Add `requirements.txt` and `requirements-dev.txt` with `pytest`, `mypy`, `pyserial`, `opcua`, and `dataclasses-json` for typed settings.

**Acceptance:** documented commands in `docs/SETUP.md` and optional `scripts/setup_venv.sh` that creates the venv when Python 3.13.7 is available.

**Status:** ✅ Completed — venv created, deps installed, docs and scripts added.

---

### [ ] Repo analysis & mapping
Read and document current flows: `ConnectionOrganiser`, `arduino_GPIO_lib`, `opc_GPIO_lib`, `arduino/*` firmware, and `sys_files/`. Produce a short diagram (text) of responsibility boundaries and protocol tokens (M*/P*).

**Acceptance:** a one-page summary in repo root `docs/ARCHITECTURE.md`.

---

### [ ] Design new driver architecture
Write a spec that splits transport interfaces from device drivers. Define a `BaseTransport` API (connect/disconnect/send/receive, events), a `DeviceDriver` API (configure, update_input, read/write helpers), and error/retry semantics. Include strict type hints and mypy-friendly signatures.

**Acceptance:** `docs/DESIGN.md` with interface signatures and example call flow.

---

### [ ] Create transport modules (skeletons)
Add separate modules `python/transports/base.py`, `python/transports/usb.py`, `python/transports/wifi.py`, `python/transports/opc.py`, `python/transports/bluetooth.py`. Each implements `BaseTransport` or a stub with the same public API as spec and full type annotations.

**Acceptance:** modules importable and unit-testable; no behavior change yet.

---

### [~] Implement Settings Manager (dynamic)
Replace/augment `sys_files/*` usage with a `python/settings_manager.py` that uses JSON as the primary, human-readable format and supports legacy plain `key:value` text files for migration. Provide runtime API to list devices, load/save device settings, validate schema (dataclasses with `dataclasses-json`), and a migration helper.

**Acceptance:** can read old `Connection_Organiser/*.data` and write new `sys_files/<device>.json` per device.

**Status:** ⚠️ In progress — basic `settings_manager.py` added with JSON/legacy support, needs testing and GPIO_Lib config support.

- [x] Test script: `python/tools/test_settings_manager.py` — lists/migrates/loads/edits and can attempt a connection

---

### [ ] Refactor ConnectionOrganiser -> BaseTransport adapter
Refactor or wrap `python/connection_organiser_with_opc.py` into a `ConnectionOrganiser` that uses the `transports` modules and `settings_manager`. Keep backwards-compatible behavior, add type-annotated wrappers and tests.

**Acceptance:** existing examples (e.g., `arduino_GPIO_lib.py` run) behave the same with minimal caller changes.

---

### [ ] Create Device driver template
Add `python/devices/template_driver.py` demonstrating how to implement `DeviceDriver` using transports and settings. Include `README` usage, typed interfaces, and a minimal example device.

**Acceptance:** template imports `transports` and `settings_manager` and shows configure/connect/loop example with type hints.

---

### [ ] Port `GPIOlib` to new driver template
Implement a new `python/devices/gpiolib.py` using the template and `transports` API, preserve `M*/P*` protocol handling and `sys_files/GPIO_Lib` parsing via new `settings_manager`. Maintain strict typing.

**Acceptance:** feature parity with old `arduino_GPIO_lib.py` (config file parsing, M100 firmware check, digital/analog read/write APIs) and example `if __name__ == '__main__'` runs similarly.

---

### [ ] Migration and compatibility helpers
Add `tools/migrate_sysfiles.py` to convert old `sys_files` text files into new JSON format. Document fallback behavior for existing scripts.

**Acceptance:** migration script can convert sample files and `gpiolib` can read migrated files transparently.

---

### [ ] Tests and mocks
Add unit tests for transports (mock serial/socket/opcua), `settings_manager`, and device template. Use `pytest`, type-checked tests (mypy), and provide example fixtures.

**Acceptance:** tests for core modules and one integration test for `gpiolib` using mocks run with `pytest` and pass locally.

---

### [ ] Docs, examples, and copilot instructions
Expand `README.md`, create `docs/` with `ARCHITECTURE.md`, `DESIGN.md`, usage examples, and update `.github/copilot-instructions.md` to reflect new structure and typing/testing conventions.

**Acceptance:** new docs present and reference code locations and quick-start commands.

---

### [ ] CI and linting (optional)
Add basic CI (GitHub Actions) to run tests, mypy, and linting on PRs. Include `requirements-dev.txt` and `pyproject.toml` that pins Python 3.13.7 for the virtual environment.

**Acceptance:** a GitHub Actions workflow that installs deps and runs `pytest` and `mypy` on PRs.

---

### [ ] Plan iterative rollout & backward compatibility
Define milestones and gating criteria for merging (e.g., skeletons merged first, then settings manager, then porting GPIOlib).

**Acceptance:** a short `docs/ROADMAP.md` with milestones, risks, and rollback steps.

---

## Notes
- Firmware (`arduino/`) is not in scope for this refactoring.
- Prefer JSON for settings (human-readable, widely supported).
- Use strict typing and `dataclasses-json` for settings models.
- Testing framework: `pytest`, type-checking: `mypy`.
