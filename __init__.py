"""PX_Device_Interfaces: Python host library and firmware for PX devices."""

__version__ = "0.0.1"

# Re-export main components from px_device_interfaces package
try:
    from .px_device_interfaces import (
        GPIO_Lib,
        ConnectionOrganiserAdapter,
        Settings,
        load_connection_settings,
        save_connection_settings,
        BaseTransport,
        MockTransport,
        create_transport_for_device,
    )

    __all__ = [
        "GPIO_Lib",
        "ConnectionOrganiserAdapter",
        "Settings",
        "load_connection_settings",
        "save_connection_settings",
        "BaseTransport",
        "MockTransport",
        "create_transport_for_device",
    ]
except ImportError as e:
    # If px_device_interfaces is not properly installed, provide a helpful error
    import sys
    print(f"Warning: Could not import px_device_interfaces submodule: {e}", file=sys.stderr)
    __all__ = []