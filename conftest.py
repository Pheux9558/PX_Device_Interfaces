import sys
from types import ModuleType

# During tests we don't want the repository-level imports to fail when
# optional runtime dependencies (like `opcua`) are not installed. Create
# lightweight stubs so collection can proceed. Real code paths that need
# these modules should still import them dynamically at runtime or be
# guarded by try/except.
def _ensure_stub(name: str, attrs: dict | None = None) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except Exception:
        mod = ModuleType(name)
        if attrs:
            for k, v in attrs.items():
                setattr(mod, k, v)
        sys.modules[name] = mod

# Stub common optional dependencies used by older entry points.
_ensure_stub("opcua", {"Client": lambda *a, **k: None})
