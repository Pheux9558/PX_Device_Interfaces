"""PX_Device_Interfaces: Python host library and firmware for PX devices."""

__version__ = "1.0.0"

# Re-export main components from px_device_interfaces package
try:
    from .px_device_interfaces import (
        GPIO_Lib,
        ConnectionOrganiserAdapter,
        BaseTransport,
        MockTransport
    )

    __all__ = [
        "GPIO_Lib",
        "ConnectionOrganiserAdapter",
        "BaseTransport",
        "MockTransport",
    ]
except ImportError as e:
    # If px_device_interfaces is not properly installed, provide a helpful error
    import sys
    print(f"Warning: Could not import px_device_interfaces submodule: {e}", file=sys.stderr)
    __all__ = []