__version__ = "0.0.1"

# Core GPIO library
from .GPIO_Lib import GPIO_Lib
from .connection_organiser_adapter import ConnectionOrganiserAdapter
from .settings_manager import (
    Settings,
    load_connection_settings,
    save_connection_settings,
    interactive_edit,
    list_devices,
)

# Transport layer
from .transports import (
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
    "interactive_edit",
    "list_devices",
    "BaseTransport",
    "MockTransport",
    "create_transport_for_device",
]
