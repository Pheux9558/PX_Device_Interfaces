"""Simple settings manager for PX_Device_Interfaces.

Responsibilities:
- Use JSON per-device files under `sys_files/<program>/<device>.json`.
- Provide typed dataclasses and (de)serialization via `dataclasses_json`.
"""
from __future__ import annotations


from pathlib import Path
from typing import Dict, List, Any
import json


ROOT_SYS = Path(__file__).resolve().parent / "sys_files"


class Settings:
    """Dynamic settings container backed by a JSON file.

    - `program` is the settings folder under `python/sys_files/` (e.g. "Connection_Organiser").
    - `device` is the device name and maps to `<device>.json`.
    - `data` is an open dict containing arbitrary keys/values for the device.
    """

    def __init__(self, program: str, device: str, data: Dict[str, Any] | None = None):
        self.program = program
        self.device = device
        self.data: Dict[str, Any] = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def delete(self, key: str) -> None:
        self.data.pop(key, None)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)

    def to_json(self, **kwargs) -> str:
        return json.dumps(self.data, **kwargs)


def load_connection_settings(device_name: str, program: str = "Connection_Organiser") -> Settings:
    """Load device settings (JSON-only).

    Returns a `Settings` object. If the JSON file does not exist an empty
    Settings object is returned and the containing directory is created.
    """
    program_dir = ROOT_SYS / program
    json_path = program_dir / f"{device_name}.json"
    if json_path.exists():
        data = json.loads(json_path.read_text())
        return Settings(program=program, device=device_name, data=data)

    # Not found — return defaults and ensure directory exists
    program_dir.mkdir(parents=True, exist_ok=True)
    return Settings(program=program, device=device_name, data={})


def save_connection_settings(device_name: str, settings: Settings, program: str = "Connection_Organiser") -> None:
    program_dir = ROOT_SYS / program
    program_dir.mkdir(parents=True, exist_ok=True)
    json_path = program_dir / f"{device_name}.json"
    json_path.write_text(settings.to_json(indent=2))


def list_devices(program: str = "Connection_Organiser") -> List[str]:
    p = ROOT_SYS / program
    if not p.exists():
        return []
    names: List[str] = []
    for f in p.iterdir():
        if f.is_file() and f.suffix == ".json":
            names.append(f.stem)
    return names


def interactive_edit(settings: "Settings") -> "Settings":
    # [ ] open in a new termianl window if script is run in a GUI environment or without CLI
    """Interactively edit a `Settings` instance on the command line.

    The editor prints the current settings as JSON, then accepts entries of
    the form `key=value`. Values are parsed as JSON where possible (so
    `timeout=10` becomes an integer, `flags=[1,2]` becomes a list). Submit an
    empty line to finish editing.
    """
    import json

    print("Current settings (empty line to finish):")
    print(json.dumps(settings.to_dict(), indent=2))
    print("Enter updates in the form key=value. Values will be interpreted as JSON when possible.")
    print("Note: Entering a key with an empty value (e.g. key=) will delete that key.")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            break
        if "=" not in line:
            print("Invalid entry, expected key=value")
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v == "":
            # empty RHS -> delete the key
            settings.delete(k)
            print(f"Removed key: {k}")
            continue
        try:
            parsed = json.loads(v)
        except Exception:
            parsed = v
        settings.set(k, parsed)

    return settings


if __name__ == "__main__":
    # Quick smoke test
    print("Existing ConnectionOrganiser devices:", list_devices())
    print("Loading example 'temp' (may create defaults)")
    s = load_connection_settings("temp")
    print(s)
