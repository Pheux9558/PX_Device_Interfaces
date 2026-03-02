from __future__ import annotations

from enum import IntEnum
import os
import struct
import struct
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional

from px_device_interfaces.transports import BaseTransport
from px_device_interfaces.transports.base import BaseTransportConfig


# region Command definitions

# Packet framing: [0xAA][CMD(2)][LEN(2)][PAYLOAD...][CHK]
# LEN is 2 bytes little-endian (allows payloads >= 256 bytes)
# CHK = (CMD + LEN + sum(PAYLOAD)) & 0xFF  (LEN used as integer)
CMD_START_BYTE                      = 0xAA

# For pin Addressings:
# LEN = length of PAYLOAD
# PAYLOAD for 0x0000-0x001F: varies based on pin address:
# PIN ADDRESS: 0-255 (1 byte each PAYLOAD)
# PIN ADDRESS: 256-65535 (2 bytes each PAYLOAD, LSB first)


# Non-Volatile memory storage:
# Settings saved to non-volatile memory (EEPROM/Flash) on the device
# are retained across power cycles. Use the SAVE_SETTINGS commands
# after configuring peripherals to store their settings. On device startup,
# these settings are loaded and peripherals are re-created automatically.
# This allows persistent configurations without needing to re-send setup commands
# from the host each time or load provide basic functionality when no host is connected.
# Note that not all devices may support non-volatile storage. If unsupported,
# SAVE_SETTINGS commands will send an ERROR response.
# Non-volatile storage is configured with the pio.ini file used during firmware
# compilation. Ensure that the device firmware has non-volatile storage enabled
# if you intend to use this feature.

# region IO CMDs
# Command definitions for setup (0x000X)
CMD_DIGITAL_OUTPUT                  = 0x0000 # Digital output, payload: (pin number)
CMD_DIGITAL_INPUT                   = 0x0001 # Digital input, payload: (pin number)
CMD_DIGITAL_INPUT_PULLUP            = 0x0002 # Digital input with internal pullup resistor enabled, payload: (pin number)
CMD_DIGITAL_INPUT_PULLDOWN          = 0x0003 # Digital input with internal pulldown resistor enabled, payload: (pin number)
CMD_ANALOG_OUTPUT                   = 0x0008 # Analog output (PWM), payload: (pin number)
CMD_ANALOG_INPUT                    = 0x0009 # Analog input, payload: (pin number)

class PinMode(IntEnum):
    OUTPUT = 0x00
    INPUT = 0x01
    INPUT_PULLUP = 0x02
    INPUT_PULLDOWN = 0x03
    ANALOG_OUTPUT = 0x08
    ANALOG_INPUT = 0x09
# ANALOG MAX command to set the max value for analog writes/reads in GPIO_Lib and on the device
CMD_ANALOG_READ_RESOLUTION          = 0x000A # Set analog resolution (ADC BITS), payload: (resolution in bits, e.g. 10 for 10-bit ADC)
CMD_ANALOG_READ_TOLERANCE           = 0x000B # Set analog read tolerance, payload: (tolerance value[e.g. 4]) update only if change exceeds this value

# Command definitions for GPIO operations (0x001X)
CMD_DIGITAL_READ                    = 0x0010 # Digital read, payload: (pin number) , returns: (value)
CMD_DIGITAL_WRITE                   = 0x0011 # Digital write, payload: (pin number, value[0/1])
CMD_ANALOG_READ                     = 0x0012 # Analog read, payload: (pin number), returns: (value)
CMD_ANALOG_WRITE                    = 0x0013 # Analog write, payload: (pin number, value[0-analog max])

# region ST7735 LCD CMDs
# Display commands by type
# ST7735 LCD commands (0x002X)
CMD_ST7735_CREATE                   = 0x0020 # Create ST7735 instance, payload: (identifier[2 bytes])
CMD_ST7735_SETUP_SPI                = 0x0022 # Setup ST7735 SPI, payload: (identifier[2 bytes], width[2 byte], height[2 byte], spi identifier[2 bytes], cs pin[1 byte], rs pin[1 byte], enable pin[1 byte], optional: backlight pin[1 byte], optional: backlight inverted[1 byte])
CMD_ST7735_CLEAR                    = 0x0025 # Clear display, payload: (identifier[2 bytes])
CMD_ST7735_SET_CURSOR               = 0x0026 # Set cursor position, payload: (identifier[2 bytes], x_pos[2 bytes], y_pos[2 bytes])
CMD_ST7735_WRITE_TEXT               = 0x0027 # Write text, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_ST7735_WRITE_TEXT_CENTER        = 0x0028 # Write centered text, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_ST7735_WRITE_BITMAP             = 0x0029 # Write bitmap (streamed), payload: (identifier[2 bytes], func[1 byte], func-specific data)
CMD_ST7735_SET_BACKLIGHT            = 0x002A # Set backlight brightness (0-255), payload: (identifier[2 bytes], brightness level)
CMD_ST7735_SET_CONTRAST             = 0x002B # Set contrast (if supported), payload: (identifier[2 bytes], contrast level)
CMD_ST7735_SET_ROTATION             = 0x002C # Set rotation (0-3), payload: (identifier[2 bytes], rotation)

# region HD44780 LCD CMDs
# HD44780 character LCD commands (0x003X)
CMD_HD44780_CREATE                  = 0x0030 # Create HD44780 instance, payload: (identifier[2 bytes])
CMD_HD44780_SETUP_I2C               = 0x0031 # Setup HD44780 I2C, payload: (identifier[2 bytes], cols[2], rows[2], i2c identifier[2], i2c address[1])
CMD_HD44780_CLEAR                   = 0x0035 # Clear display, payload: (identifier[2 bytes])
CMD_HD44780_SET_CURSOR              = 0x0036 # Set cursor position, payload: (identifier[2 bytes], col[2], row[2])
CMD_HD44780_WRITE_TEXT              = 0x0037 # Write text, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_HD44780_SET_BACKLIGHT           = 0x003A # Set backlight (0/1 or 0-255), payload: (identifier[2 bytes], level)

# region AiP31068L LCD CMDs
# AiP31068L character LCD commands (0x004X)
CMD_AIP31068L_CREATE                = 0x0040 # Create AiP31068L instance, payload: (identifier[2 bytes])
CMD_AIP31068L_SETUP_I2C             = 0x0041 # Setup AiP31068L I2C, payload: (identifier[2 bytes], cols[2], rows[2], i2c identifier[2], i2c address[1])
CMD_AIP31068L_CLEAR                 = 0x0045 # Clear display, payload: (identifier[2 bytes])
CMD_AIP31068L_SET_CURSOR            = 0x0046 # Set cursor position, payload: (identifier[2 bytes], col[2], row[2])
CMD_AIP31068L_WRITE_TEXT            = 0x0047 # Write text, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_AIP31068L_SET_BACKLIGHT         = 0x004A # Set backlight (0/1 or 0-255), payload: (identifier[2 bytes], level)

# region SSD1306 OLED CMDs
# SSD1306 OLED commands (0x005X)
CMD_SSD1306_CREATE                  = 0x0050 # Create SSD1306 instance, payload: (identifier[2 bytes])
CMD_SSD1306_SETUP_I2C               = 0x0051 # Setup SSD1306 I2C, payload: (identifier[2 bytes], width[2], height[2], i2c identifier[2], i2c address[1])
CMD_SSD1306_SETUP_SPI               = 0x0052 # Setup SSD1306 SPI, payload: (identifier[2 bytes], width[2], height[2], spi identifier[2], cs pin[1], dc pin[1], reset pin[1])
CMD_SSD1306_CLEAR                   = 0x0055 # Clear display, payload: (identifier[2 bytes])
CMD_SSD1306_SET_CURSOR              = 0x0056 # Set cursor position, payload: (identifier[2 bytes], x_pos[2], y_pos[2])
CMD_SSD1306_WRITE_TEXT              = 0x0057 # Write text, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_SSD1306_WRITE_BITMAP            = 0x0059 # Write monochrome bitmap (streamed), payload: (identifier[2], func[1], func-specific data)
CMD_SSD1306_SET_BRIGHTNESS          = 0x005A # Set brightness/contrast, payload: (identifier[2 bytes], level)
CMD_SSD1306_SET_ROTATION            = 0x005B # Set rotation (0-3), payload: (identifier[2 bytes], rotation)

# region Touchscreen CMDs
# Command definitions for Touchscreen operations (0x00FX)
CMD_TOUCHSCREEN_CREATE              = 0x00F0 # Create Touchscreen instance, payload: (identifier[2 bytes])
# Command definitions for Touchscreen I2C setup and configuration is not yet defined
CMD_TOUCHSCREEN_SETUP_SPI           = 0x00F2 # Setup Touchscreen SPI, payload: (identifier[2 bytes], spi identifier[2 bytes], cs pin[1 byte], dc pin[1 byte], reset pin[1 byte])
CMD_TOUCHSCREEN_READ_XY             = 0x00F5 # Read touchscreen X,Y coordinates, payload: (identifier[2 bytes]), returns: (x[2 bytes], y[2 bytes], pressed[1 byte])
# [ ] TODO Save Touchscreen settings command to save Touchscreen configuration to non-volatile memory for automatic setup on startup
# CMD_TOUCHSCREEN_SAVE_SETTINGS       = 0x00FF # Save Touchscreen settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region Servo CMDs
# Command definitions for Servo operations (0x010X)
CMD_SERVO_ATTACH                    = 0x0100 # Attach servo to pin
CMD_SERVO_DETACH                    = 0x0101 # Detach servo from pin
CMD_SERVO_WRITE                     = 0x0102 # Write angle to servo

# region FastLed CMDs
# APA102 (DotStar) LED commands (0x011X)
CMD_APA102_CREATE                   = 0x0110 # Create APA102 instance, payload: (identifier[2 bytes])
CMD_APA102_SETUP                    = 0x0111 # Setup APA102, payload: (identifier[2 bytes], data_pin, clock_pin, num_leds[2 bytes])
CMD_APA102_SHOW                     = 0x0115 # Stream LED data to APA102 and update, payload: (identifier[2 bytes], LED RGB data bytes...)
CMD_APA102_SET_BRIGHTNESS           = 0x0116 # Set APA102 brightness, payload: (identifier[2 bytes], brightness[1 byte])

# WS2812 (NeoPixel) LED commands (0x012X)
CMD_WS2812_CREATE                   = 0x0120 # Create WS2812 instance, payload: (identifier[2 bytes])
CMD_WS2812_SETUP                    = 0x0121 # Setup WS2812, payload: (identifier[2 bytes], data_pin, num_leds[2 bytes])
CMD_WS2812_SHOW                     = 0x0125 # Stream LED data to WS2812 and update, payload: (identifier[2 bytes], LED RGB data bytes...)
CMD_WS2812_SET_BRIGHTNESS           = 0x0126 # Set WS2812 brightness, payload: (identifier[2 bytes], brightness[1 byte])


class UARTParity(IntEnum):
    NONE = 0x00
    EVEN = 0x01
    ODD = 0x02


class UARTFlowControl(IntEnum):
    NONE = 0x00
    RTS = 0x01
    CTS = 0x02
    RTS_CTS = 0x03


class SPIMode(IntEnum):
    MODE0 = 0x00
    MODE1 = 0x01
    MODE2 = 0x02
    MODE3 = 0x03


# region UART CMDs
# Command definitions for UART operations (0x020X)
CMD_UART_CREATE                     = 0x0200 # Create UART instance, payload: (identifier[2 bytes])
CMD_UART_SET_PARITY                 = 0x0201 # Set UART parity, payload: (identifier[2 bytes], parity[1 byte])
CMD_UART_SET_STOPBITS               = 0x0202 # Set UART stop bits, payload: (identifier[2 bytes], stopbits[1 byte])
CMD_UART_SET_DATA_BITS              = 0x0203 # Set UART data bits, payload: (identifier[2 bytes], databits[1 byte])
CMD_UART_SET_FLOWCONTROL            = 0x0204 # Set UART flow control, payload: (identifier[2 bytes], flowcontrol[1 byte])
CMD_UART_SET_BAUDRATE               = 0x0205 # Set UART baudrate, payload: (identifier[2 bytes], baudrate[4 bytes])
CMD_UART_SET_PIN_TX                 = 0x0206 # Set UART TX pin, payload: (identifier[2 bytes], pin number)
CMD_UART_SET_PIN_RX                 = 0x0207 # Set UART RX pin, payload: (identifier[2 bytes], pin number)
CMD_UART_READ                       = 0x0208 # UART read, payload: (identifier[2 bytes], length), returns: (data bytes)
CMD_UART_WRITE                      = 0x0209 # UART write, payload: (identifier[2 bytes], data bytes...)
# [ ] TODO Save UART settings command to save UART configuration to non-volatile memory for automatic setup on startup
# CMD_UART_SAVE_SETTINGS              = 0x020F # Save UART settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region I2C CMDs
# Command definitions for I2C operations (0x021X)
CMD_I2C_CREATE                      = 0x0210 # Create I2C instance, payload: (identifier[2 bytes])
CMD_I2C_SET_FREQUENCY               = 0x0211 # Set I2C frequency, payload: (identifier[2 bytes], frequency[4 bytes])
CMD_I2C_SET_PIN_CLOCK               = 0x0212 # Set I2C clock pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_SET_PIN_DATA                = 0x0213 # Set I2C data pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_READ                        = 0x0214 # I2C read, payload: (identifier[2 bytes], device address[1 byte], length), returns: (data bytes)
CMD_I2C_WRITE                       = 0x0215 # I2C write, payload: (identifier[2 bytes], device address[1 byte], data bytes...)
CMD_I2C_WRITE_READ                  = 0x0216 # I2C write then read, payload: (identifier[2 bytes], device address[1 byte], write_len[2 bytes], write bytes..., read_len[2 bytes]), returns: (identifier[2 bytes], data bytes)
CMD_I2C_FULL_ADDRESS_SCAN           = 0x021E # I2C full address scan, payload: (identifier[2 bytes]), returns: (identifier[2 bytes], list of device addresses found[1 byte each])
CMD_I2C_SET_BUS                     = 0x021D # Set I2C bus (Wire=0 or Wire1=1), payload: (identifier[2 bytes], bus[1 byte])
# [ ] TODO Save I2C settings command to save I2C configuration to non-volatile memory for automatic setup on startup
CMD_I2C_SAVE_SETTINGS               = 0x021F # Save I2C settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region SPI CMDs
# Command definitions for SPI operations (0x022X)
CMD_SPI_CREATE                      = 0x0220 # Create SPI instance, payload: (identifier[2 bytes])
CMD_SPI_SET_FREQUENCY               = 0x0221 # Set SPI frequency, payload: (identifier[2 bytes], frequency[4 bytes])
CMD_SPI_SET_MODE                    = 0x0222 # Set SPI mode, payload: (identifier[2 bytes], mode[1 byte])
CMD_SPI_SET_PIN_CLOCK               = 0x0223 # Set SPI clock pin, payload: (identifier[2 bytes], pin number)
CMD_SPI_SET_PIN_MOSI                = 0x0224 # Set SPI MOSI pin, payload: (identifier[2 bytes], pin number)
CMD_SPI_SET_PIN_MISO                = 0x0225 # Set SPI MISO pin, payload: (identifier[2 bytes], pin number)
CMD_SPI_READ                        = 0x0226 # SPI transfer, payload: (identifier[2 bytes], data bytes...), returns: (data bytes)
CMD_SPI_WRITE                       = 0x0227 # SPI write, payload: (identifier[2 bytes], data bytes...)

# [ ] TODO Save SPI settings command to save SPI configuration to non-volatile memory for automatic setup on startup
# CMD_SPI_SAVE_SETTINGS               = 0x022F # Save SPI settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])
# CS pin lives inside peripherals since multiple CS pins may be used per SPI instance or can be managed manually by the user via digital writes.

# region Bluetooth CMDs
# Command definitions for bluetooth operations (0x027X)
# [ ] Bluetooth commands can be defined here

# region Wi-Fi CMDs
# Command definitions for WiFi operations (0x028X)
# [ ] WiFi commands can be defined here



# # Command definitions for GPIO_Lib setup (0x030X)
# GPIO_Lib comunication interface setup. UART, Bluetooth and WiFi transports are supported.
CMD_SETUP_GPIO_LIB_UART              = 0x0300 # Setup GPIO_Lib communication over UART, payload: (uart identifier[2 bytes], baudrate[4 bytes]) 
CMD_SETUP_GPIO_LIB_BLUETOOTH         = 0x0304 # Setup GPIO_Lib communication over Bluetooth, payload: (bluetooth identifier[2 bytes], device name length[1 byte], device name bytes...)
CMD_SETUP_GPIO_LIB_WIFI              = 0x0308 # Setup GPIO_Lib communication over WiFi, payload: (wifi identifier[2 bytes], ssid length[1 byte], ssid bytes..., password length[1 byte], password bytes..., ip address [4 bytes], port [2 bytes])
CMD_SETUP_GPIO_LIB_ETHERNET          = 0x030C # Setup GPIO_Lib communication over Ethernet, payload: (ethernet identifier[2 bytes], ip address [4 bytes], port [2 bytes])

# Command definitions for OneWire operations (0x023X)
# [ ] OneWire commands can be defined here

# Command definitions for CAN bus operations (0x024X)
# [ ] CAN bus commands can be defined here

# Future command ranges:
# [ ] Define additional command ranges as needed
# e.g. Custom peripheral commands (0x020X - 0x02FX)



# region Return codes
# General response codes
CMD_DEVICE_OK                       = 0x1000 # General OK response (e.g. Response to valid commands or acknowledgements for actions)
CMD_DEVICE_ERROR                    = 0x1001 # General ERROR response (e.g. Response to invalid commands or parameters)

# Controll codes
CMD_FIRMWARE_RESET                  = 0xFFFC # Reset the device, no payload. Response with CMD_BANNER_GPIO_READY after reboot and initialization. Note: this command will cause the device to disconnect and reconnect if using USB CDC, so the transport may need to be re-established on the host side after sending this command.
CMD_FIRMWARE_BUILD_FLAGS            = 0xFFFD # Response with build flags, returns: (build flags string in UTF-8)
CMD_FIRMWARE_NAME                   = 0xFFFE # Response with firmware name, returns (name string in UTF-8) # Name of the device configuration
CMD_FIRMWARE_VERSION                = 0xFFFF # Response with firmware version, returns: (major, minor, patch)

# Controll Banners
CMD_BANNER_GPIO_READY               = "GPIO_READY" # GPIO_READY banner indicating device is ready for operation
# endregion Return codes from device


# region GPIO_Lib class
class GPIO_Lib:
    """Binary-protocol GPIO library for Arduino-like controllers.

        - Uses a transport constructed from a `transport_config` dataclass.
        - Provides Arduino-like configuration helpers: `pin_mode()` / `pinMode()`,
            `attach_servo()` and `detach_servo()` to configure pins at runtime.
        - Maintains mirrors for inputs, outputs, servos and an LCD buffer.

    NOTE: This API requires a `transport_config` object and does not accept
    legacy transport kwargs (transport_type/port/baud/loopback/timeout).

    auto_io (bool): when True, writes (digital/analog/servo/lcd) are
      immediately sent to the controller and incoming updates are applied
      automatically. When False, the user must call `sync()` to push and
      pull updates.
    """
    # region Initialization
    # [ ] TODO refactor formate (__init__())
    def __init__(
        self,
        transport_config: BaseTransportConfig,
        require_ack_on_send: bool = True,
        send_ack_timeout: float = 2.0,
        send_ready_timeout: float = 1.0,
        loop_delay: float = 0.0005,
        debug_enabled: bool | None = None,
    ):
        # Required parameters
        if transport_config is None:
            raise ValueError("transport_config must be provided and be a BaseTransportConfig instance")

        self.handshake_enabled = True
        self.handshake_raise_on_timeout = True
        self.handshake_timeout = 5.0
        self.transport_config = transport_config

        self.reset_on_start = True


        # [ ] TODO test auto_io behavior and sync() calls
        self.auto_io = self.transport_config.auto_io

        self.debug_enabled = debug_enabled or self.transport_config.debug

        self.debug_ok_received = 0
        self.last_send_data: Optional[bytes] = None
        self.total_sent_bytes = 0
        self.total_received_bytes = 0

        self.firmware_version: Optional[tuple[int, int, int]] = None
        self.firmware_name: Optional[str] = None
        self.firmware_build_flags: List[str] = []

        # mirrors (dict-based, dynamic)
        # structure: { name: { 'pin': int, 'value': int, 'type': 'digital'|'analog' } }
        self.inputs: Dict[str, Dict] = {}
        self.outputs: Dict[str, Dict] = {}
        self.pin_to_name: Dict[int, str] = {}
        self.servo_array: Dict[int, int] = {}
        self.lcd_lines: List[str] = []

        self._transport: Optional[BaseTransport] = None
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None
        self.stopReceiveWorkerRequested = False
        self._buf = bytearray()

        # send worker / buffering
        self._send_q: "queue.Queue[tuple[bytes, bool]]" = queue.Queue()
        self._send_thread: Optional[threading.Thread] = None
        self._send_in_progress = False
        self.require_ack_on_send = bool(require_ack_on_send)
        self.send_ack_timeout = float(send_ack_timeout)
        self.send_ready_timeout = float(send_ready_timeout)
        self.loop_delay = float(loop_delay)

        # OK frame counter + condition for waiters
        self._ok_cv = threading.Condition()
        # readiness condition (device sent GPIO_READY banner)
        self._ready = False
        self._ready_cv = threading.Condition()
        # record per-OK timestamps for plotting/diagnostics (list of datetime objects)
        # Use maxlen to prevent unbounded memory growth in long-running processes
        self._max_ok_timestamps = 1000  # Max 1000 timestamps (~50KB)
        self._ok_timestamps: List[datetime] = []
        # response capture for request/response commands (UART/I2C/SPI reads)
        self._resp_cv = threading.Condition()
        self._responses: Dict[tuple[int, int], bytes] = {}

    # region Debug handling
    def log_debug_message(self, msg: str, timestamp: Optional[str] = None) -> None:
        """Print debug messages with timestamp."""
        timestamp = timestamp or datetime.now().isoformat(timespec='milliseconds')
        if self.debug_enabled:
            print(f"{timestamp} - GPIO_Lib: {msg}")

    def setDebugFunction(self, debug_function) -> None:
        """Set a custom debug function to handle debug messages.
        Arguments:
          - `debug_function`: a callable that takes `msg: str` and `timestamp: Optional[str]`
        """
        self.log_debug_message = debug_function
    
    # region transport config
    def setTransportConfig(self, transport_config: BaseTransportConfig) -> None:
        """Set a new transport configuration. The transport will be
        created from this config on the next `start()` call.
        Remember to stop the GPIO_Lib instance before changing
        the transport configuration with `stop()`.
        Arguments:
          - `transport_config`: a BaseTransportConfig instance
        """
        if not isinstance(transport_config, BaseTransportConfig):
            raise ValueError("transport_config must be a BaseTransportConfig instance")
        self.transport_config = transport_config
    
    def getTransportConfig(self) -> BaseTransportConfig:
        """Return the current transport configuration."""
        return self.transport_config

    # region Handshake config
    def setHandshakeEnabled(self, enabled: bool) -> None:
        """Enable or disable the handshake (GPIO_READY banner wait) on start().
        Arguments:
          - `enabled`: True to enable handshake, False to disable
        """
        self.handshake_enabled = bool(enabled)
    
    @property
    def isHandshakeEnabled(self) -> bool:
        """Return True if handshake is enabled, False if disabled."""
        return self.handshake_enabled

    def setHandshakeTimeout(self, timeout: float) -> None:
        """Set the handshake timeout in seconds.
        Arguments:
          - `timeout`: timeout in seconds (float)
        """
        self.handshake_timeout = float(timeout)

    def getHandshakeTimeout(self) -> float:
        """Return the handshake timeout in seconds."""
        return self.handshake_timeout

    # region Auto IO config
    def setAutoIO(self, auto_io: bool) -> None:
        """Set the auto_io flag.
        Arguments:
          - `auto_io`: True to enable auto IO, False to disable
        """
        self.auto_io = bool(auto_io)

    @property
    def isAutoIO(self) -> bool:
        """Return True if auto_io is enabled, False if disabled."""
        return self.auto_io

    # region Debug config
    def setDebugEnabled(self, enabled: bool) -> None:
        """Enable or disable debug messages.
        Arguments:
          - `enabled`: True to enable debug, False to disable
        """
        self.debug_enabled = bool(enabled)

    @property
    def isDebugEnabled(self) -> bool:
        """Return True if debug is enabled, False if disabled."""
        return self.debug_enabled

    # region Ack config
    def enableAckOnSend(self, flag: bool) -> None:
        """Enable or disable waiting for device OK between sends."""
        self.require_ack_on_send = bool(flag)

    @property
    def isAckOnSendEnabled(self) -> bool:
        """Return True if waiting for device OK between sends is enabled."""
        return self.require_ack_on_send
    
    # region Loop delay config
    def setLoopDelay(self, delay: float) -> None:
        """Adjust the small delay between consecutive sends (seconds)."""
        self.loop_delay = float(delay)
    
    def getLoopDelay(self) -> float:
        """Return the current loop delay between sends (seconds)."""
        return self.loop_delay

    # region OK timestamps
    def getOkTimestamps(self) -> List[datetime]:
        """Return a copy of recorded OK timestamps (datetime objects)."""
        return list(self._ok_timestamps)
    
    # region Read Firmware
    def requestFirmwareInfo(self, timeout: float = 5.0) -> bool:
        """
        Request firmware information (name, version, build flags) from the device.
        The information will be stored in the instance variables:
          - self.firmware_name (str)
          - self.firmware_version (tuple of (major, minor, patch))
          - self.firmware_build_flags (list of str)
        returns True if the information was successfully retrieved, False otherwise.
        """
        if not self._transport or not self._transport.is_connected:
            self.log_debug_message("requestFirmwareInfo: transport not connected")
            return False
        # Delete any existing firmware info to ensure we get fresh data
        self.firmware_name = None
        self.firmware_version = None
        self.firmware_build_flags = []
        # Send requests for firmware information; responses will be handled in the receive worker and stored in instance variables
        self._add_packet_to_send_queue(self._build_packet(CMD_FIRMWARE_NAME, b''))
        self._add_packet_to_send_queue(self._build_packet(CMD_FIRMWARE_VERSION, b''))
        self._add_packet_to_send_queue(self._build_packet(CMD_FIRMWARE_BUILD_FLAGS, b''))
        # Wait for responses with a timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.firmware_name and self.firmware_version and self.firmware_build_flags:
                return True
            time.sleep(0.1)
        self.log_debug_message("requestFirmwareInfo: timeout waiting for firmware information")
        return False


    # region Legacy connect/disconnect
    def connect(self) -> bool:
        """Legacy connect() method; use start() instead."""
        self.log_debug_message("connect() called (legacy); starting GPIO_Lib...")
        return self.start()

    def disconnect(self) -> None:
        """Legacy disconnect() method; use stop() instead."""
        self.log_debug_message("disconnect() called (legacy); stopping GPIO_Lib...")
        self.stop()

    # region Start GPIO_Lib
    # [x] TODO refactor formate (Start/Stop)
    def start(self) -> bool:
        """Start GPIO_Lib operation and worker threads."""
        if self._running:
            return False # already running
        
        # Create transport from the provided dataclass config (no kwargs path)
        if not hasattr(self.transport_config, "create_transport"):
            raise ValueError("transport_config must implement create_transport() and produce a BaseTransport instance")
        self._transport = self.transport_config.create_transport()
        if not self._transport:
            raise RuntimeError("no transport available from transport_config.create_transport()")

        # Link debug print functions
        self._transport.set_debug_function(self.log_debug_message)

        # attempt connect and ensure the transport reports connected state
        if not self._transport.connect():
            raise RuntimeError("transport failed to connect")
        if not self._transport.is_connected:
            raise RuntimeError("transport is not connected after connect()")

        # set thread loop flag
        self._running = True

        # start send thread
        self._send_thread = threading.Thread(target=self._send_worker, name="GPIO_send", daemon=True)
        self._send_thread.start()
        # start recv thread
        self._recv_thread = threading.Thread(target=self._recv_worker, name="GPIO_recv", daemon=True)
        self._recv_thread.start()

        # Reset on startup and invoke handshake to wait for ready banner
        # or skip directly to ready state if handshake disabled
        if self.reset_on_start:
            self.resetDevice()


        # Check thread status and log
        if not self._send_thread.is_alive():
            self.log_debug_message("send thread failed to start")
            self._running = False
            return False
        if not self._recv_thread or not self._recv_thread.is_alive():
            self.log_debug_message("recv thread failed to start")
            self._running = False
            return False
        
        # Wait till config is transmitted to device
        self.await_send_empty()

        self.log_debug_message("#### GPIO_Lib started successfully ####")
        return True     # started successfully
    
    # region Stop GPIO_Lib
    def stop(self, timeout: float = 5.0) -> None:
        """Stop GPIO_Lib operation and worker threads."""
        if not self._running:
            self.log_debug_message("stop() called but GPIO_Lib not running")
            return

        self.await_send_empty(timeout=timeout)
        # clear running flag
        self._running = False

        # wait for threads to terminate
        if self._send_thread:
            self.log_debug_message("Waiting for send thread to terminate...")
            self._send_thread.join(0.5)
        if self._recv_thread:
            self.log_debug_message("Waiting for recv thread to terminate...")
            self._recv_thread.join(0.5)

        # disconnect transport
        if self._transport:
            self._transport.disconnect()

        self.log_debug_message("GPIO_Lib stopped")
        print("") # newline for readability after stop
        # Print summary of debug info
        print(f"Total sent: {self.total_sent_bytes} bytes, Total received: {self.total_received_bytes} bytes")
        print(f"Total OK frames received: {self.debug_ok_received}")

    # region Handshake / Ready Banner
    # [ ] TODO refactor formate (_await_device_ready())
    def _await_device_ready(self, timeout: float = 5.0) -> bool:
        """Wait up to `timeout` seconds for a textual `GPIO_READY` banner from device.
        Note: _recv_worker must not be running while this is called.
        Uses `transport.receive()` (text decode) to look for the banner. Returns
        True if detected, False on timeout.
        """
        if not self._transport or not self._transport.is_connected:
            self.log_debug_message("await_device_ready: transport not connected")
            return False

        # validate timeout (larger than zero)
        if timeout <= 0:
            timeout = 1.0
            self.log_debug_message("await_device_ready: invalid timeout, using 1.0s")
        
        # check recv_worker not active
        if self._recv_thread and self._recv_thread.is_alive():
            raise RuntimeError("_await_device_ready() called while recv_worker is running")

        # calculate end time
        end = time.time() + float(timeout)
        self.log_debug_message("Waiting for device ready banner...")

        # loop until timeout
        while time.time() < end:
            # delay to throttle loop
            time.sleep(0.05)

            # Read bytess from transport
            received_data = self._transport.receive_bytes()
            if not received_data:
                continue
            
            # decode as text, ignoring errors
            decoded_received_data = received_data.decode(errors="ignore")
            
            # check for ready banner
            if CMD_BANNER_GPIO_READY in decoded_received_data:
                self.log_debug_message(f"received ready banner data: {decoded_received_data.strip()}")

                # mark readiness for send worker and notify waiters
                with self._ready_cv:
                    self._ready = True
                    self._ready_cv.notify_all()
                return True
        if self.handshake_raise_on_timeout:
            raise TimeoutError("Timeout waiting for device ready banner")
        self.log_debug_message("Timeout waiting for device ready banner")
        return False

    # region Packet building
    def _build_packet(self, cmd: int, payload: bytes = b"") -> bytes:
        """Build a framed packet for sending.
        Calculates length and checksum automatically.
        """
        length = len(payload)
        chk = (int(cmd) + length + sum(payload)) & 0xFF
        cmd_bytes = int(cmd).to_bytes(2, "little")
        len_bytes = int(length).to_bytes(2, "little")
        if self.debug_enabled:
            self.log_debug_message(
                f"Building packet: CMD=0x{int(cmd):04X}, LEN={length}, PAYLOAD={payload.hex()}, CHK=0x{chk:02X}"
            )
        return bytes([CMD_START_BYTE]) + cmd_bytes + len_bytes + payload + bytes([chk])

    # region Packet parsing
    @staticmethod
    def _parse_frame(buf: bytearray) -> Optional[tuple[int, bytes]]:
        """Attempt to parse a single frame from buf. If a complete valid frame
        is present, remove it from buf and return (cmd, payload). Otherwise
        return None.
        """
        # minimum frame: start(1) + cmd(2) + len(2) + chk(1) => 6 bytes
        if len(buf) < 6:
            return None

        # find start byte and align buffer
        try:
            idx = buf.index(CMD_START_BYTE)
        except ValueError:
            buf.clear()
            return None
        if idx > 0:
            del buf[:idx]
            if len(buf) < 5:
                return None

        # now at start; ensure header (cmd + len) present
        if len(buf) < 5:
            return None

        cmd = int.from_bytes(bytes(buf[1:3]), "little")
        length = int.from_bytes(bytes(buf[3:5]), "little")
        total_len = 1 + 2 + 2 + length + 1
        if len(buf) < total_len:
            return None

        payload = bytes(buf[5 : 5 + length])
        chk = buf[5 + length]
        if ((cmd + length + sum(payload)) & 0xFF) != chk:
            # checksum failed: discard the start byte and retry
            del buf[0]
            return None

        # valid frame; remove it and return
        del buf[:total_len]
        return cmd, payload
    
    # region Validate packet
    @staticmethod
    def _validatePacket(pack:bytes) -> bool:
        """Validate a framed packet's checksum. Returns True if valid, False if invalid."""
        if len(pack) < 6:
            return False
        if pack[0] != CMD_START_BYTE:
            return False
        cmd = int.from_bytes(pack[1:3], "little")
        length = int.from_bytes(pack[3:5], "little")
        if len(pack) != 1 + 2 + 2 + length + 1:
            return False
        payload = pack[5 : 5 + length]
        chk = pack[5 + length]
        return ((cmd + length + sum(payload)) & 0xFF) == chk

    # region Queueing Packets
    def _add_packet_to_send_queue(self, packet: bytes, wait_ack: bool = False, validate: bool = True) -> bool:
        """Enqueue a framed packet for delivery by the send worker.

        Returns True when enqueued (convenience for callers/tests).
        """
        # Sanity check packet for external callers
        if validate and self._validatePacket(packet) is False:
            raise ValueError("enqueue_packet: invalid packet checksum")

        if self.debug_enabled:
            self.log_debug_message(f"enqueue packet len={len(packet)} wait_ack={wait_ack} hex={packet.hex()}")
        self._send_q.put((packet, bool(wait_ack)))
        return True
    
    # region Await send empty
    def await_send_empty(self, timeout: float | None = None) -> bool:
        """Block until the send queue is empty and any in-progress send completes.

        Returns True if the buffer emptied, False if timed out.
        """
        if self._send_q.empty() and not self._send_in_progress:
            self.log_debug_message("Send queue already empty and no send in progress")
            return True
        
        self.log_debug_message("Awaiting send queue to empty...")
        end = time.time() + float(timeout) if timeout is not None else None
        while True:
            if not self._transport or not self._transport.is_connected:
                self.log_debug_message("Transport not connected")
                return False
            if not self._running:
                self.log_debug_message("GPIO_Lib not running")
                return False            
            if self._send_q.empty() and not self._send_in_progress:
                self.log_debug_message("Send queue empty and no send in progress")
                return True
            if end is not None and time.time() > end:
                self.log_debug_message("Awaiting send queue timed out")
                return False
            time.sleep(0.001)

    # region send worker
    def _send_worker(self) -> None:
        """Background worker that serializes access to the transport and optionally
        waits for a device OK frame after each send (controlled by per-packet flag or
        the `send_wait_for_ok_by_default` setting).
        """
        if not self._transport:
            raise RuntimeError("send_worker: transport not initialized")
        
        self.log_debug_message("send_worker started")

        while self._running:
            try:
                packet, wait_ack = self._send_q.get(timeout=0.01)
            except Exception:
                # no packet, continue
                time.sleep(self.loop_delay)
                continue

            self._send_in_progress = True
            try:
                # wait for device READY banner (or timeout)
                with self._ready_cv:
                    ready_waited = self._ready_cv.wait_for(lambda: self._ready, timeout=self.send_ready_timeout)
                if not ready_waited and self.debug_enabled:
                    self.log_debug_message("send_worker: timed out waiting for device READY (proceeding)")

                # actually send bytes
                if self.debug_enabled:
                    self.log_debug_message(f"sending(hex): {packet.hex()}")
                try:
                    self.total_sent_bytes += len(packet)
                    self.last_send_data = packet
                    self._transport.send(packet)
                except Exception as e:
                    # On "[ERRNO 5] Input/Output error" => dissconect
                    # [ ] TODO Fix broken exception
                    if "input/output error" in str(e).lower():
                        self.log_debug_message("I/O Reeoe detected")
                        self.stop()
                    

                    if self.debug_enabled:
                        self.log_debug_message(f"send error: {e}")
                # optionally wait for device OK
                if bool(wait_ack or self.require_ack_on_send):
                    start = self.debug_ok_received
                    with self._ok_cv:
                        waited = self._ok_cv.wait_for(lambda: self.debug_ok_received > start, timeout=self.send_ack_timeout)
                    if not waited and self.debug_enabled:
                        self.log_debug_message("send_worker: timed out waiting for device OK")
                # mark task done
                self._send_q.task_done()
                
            finally:
                self._send_in_progress = False
        self.log_debug_message("send_worker exiting")

    # region recv worker
    def _recv_worker(self) -> None:
        """Background worker that receives bytes from the transport,
        parses frames, and dispatches them to the packet handler.
        """

        if not self._transport:
            raise RuntimeError("recv_worker: transport not initialized")
        
        self.log_debug_message("recv_worker started")

        while self._running:
            if self.stopReceiveWorkerRequested:
                break
            # small pause to yield to other threads
            time.sleep(self.loop_delay)

            data = self._transport.receive_bytes()
            if not data:
                continue
            self.log_debug_message(f"Received data: {data!r}")
            self.total_received_bytes += len(data)

            # Some firmware builds emit plain-text debug lines (CRLF terminated)
            # on the same serial port when compiled with DEBUG. Detect and
            # surface these debug lines to the user, removing them from the
            # byte stream so they don't interfere with binary frame parsing.


            # extract any leading CRLF-terminated ASCII debug lines
            remaining = bytes(data)

            while True:
                # look for CRLF or LF as line terminator
                idx = remaining.find(b"\r\n")
                term_len = 2
                if idx == -1:
                    idx = remaining.find(b"\n")
                    term_len = 1 if idx != -1 else -1
                if idx == -1:
                    break
                line = remaining[:idx]
                # Heuristic: treat short printable lines as debug text
                if len(line) > 0 and all(32 <= b < 127 for b in line):
                    try:
                        s = line.decode("utf-8", errors="replace")
                    except Exception:
                        s = None
                    if s is not None:
                        if self.debug_enabled:
                            print("device-debug:", s)
                        
                        # remove the debug line and continue
                        remaining = remaining[idx + term_len :]
                        continue
                # not a debug line; stop scanning
                break

            # whatever remains (possibly empty) is binary and should be parsed
            if remaining:
                self._buf.extend(remaining)

            while True:
                res = self._parse_frame(self._buf)
                if not res:
                    break
                cmd, payload = res
                self._handle_packet(cmd, payload)

        self.log_debug_message("recv_worker exiting")


    # region Reset Device
    def resetDevice(self) -> None:
        """Send a reset command to the device via the firmware protocol. 
        This will cause the device to reboot, so the transport may disconnect and reconnect (e.g. USB CDC). 
        After sending the reset command, this method will wait for the device to become ready again (via handshake) before returning. 
        If the handshake is disabled, it will simply wait a fixed delay after sending the reset command.
        """
        if not self._transport:
            raise RuntimeError("resetDevice: transport not initialized")
        
        try:
            self._add_packet_to_send_queue(self._build_packet(CMD_FIRMWARE_RESET, b""), wait_ack=False)
            # wait for device ok response to ensure the reset command was processed before proceeding with thread shutdown and handshake
            with self._ok_cv:
                start_ok_count = self.debug_ok_received
                waited = self._ok_cv.wait_for(lambda: self.debug_ok_received > start_ok_count, timeout=self.handshake_timeout)
            if not waited and self.debug_enabled:
                self.log_debug_message("resetDevice: timed out waiting for device OK after sending firmware reset command")
            self.log_debug_message("Device reset command sent via firmware protocol")

            self._handshake_after_boot_reset()
        except Exception as e:
            self.log_debug_message(f"Error sending firmware reset command: {e}")
        

    # region Handshake after boot reset
    def _handshake_after_boot_reset(self) -> None:
        if not self.handshake_enabled:
            self.log_debug_message("Handshake disabled; skipping post-reset handshake")
            return

        # Stop receive thread to avoid processing incoming data during reset
        if self._recv_thread and self._recv_thread.is_alive():
            self.log_debug_message("Waiting for receive thread to stop before proceeding with reset...")
            self.stopReceiveWorkerRequested = True
            self._recv_thread.join(2.0)  # Increased timeout from 0.5 to 2.0 seconds
            if self._recv_thread.is_alive():
                self.log_debug_message("ERROR: Receive thread did not stop in time; cannot proceed safely")
                raise RuntimeError("Receive thread did not stop - cannot safely restart")
            else:
                self.log_debug_message("Receive thread stopped successfully")
        
        # If handshake is enabled, wait for the device to become ready again after reset
        if self.handshake_enabled:
            self.log_debug_message("Waiting for device to become ready after reset...")
            ok = self._await_device_ready(timeout=self.handshake_timeout)
            self.log_debug_message("Post-reset handshake: ready=" + str(ok))
            # set readiness flag from handshake probe
            with self._ready_cv:
                self._ready = bool(ok)
                if self._ready:
                    self._ready_cv.notify_all()
            if not ok:
                self.log_debug_message("Device did not become ready after reset within timeout")
        else:
            self.log_debug_message("Handshake disabled; assuming device is ready after reset")
            # set readiness flag
            with self._ready_cv:
                self._ready = True
                self._ready_cv.notify_all()
        
        # start receive thread again if it was stopped
        if self.stopReceiveWorkerRequested:
            self.stopReceiveWorkerRequested = False
            self._recv_thread = threading.Thread(target=self._recv_worker, daemon=True)
            self._recv_thread.start()
            self.log_debug_message("Receive thread started after reset")



    # region Hardware Peripherals
    """
    This section declares every device/peripheral you can controll via GPIO_Lib
    The default herachy is:
    GPIO_Lib instance:
        - device/peripheral main class:
                - Different types/versions of this device/peripheral
    
    """


    # region FastLED namespace
    class FastLED:
        """FastLED type namespace (APA102, WS2812)."""


        # region APA102
        class FastLEDAPA102:
            """APA102 (DotStar) LED strip handler - requires data and clock pins."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                data_pin: int,
                clock_pin: int,
                led_count: int,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.FastLED.FastLEDAPA102.total_instances
                gpio_lib.FastLED.FastLEDAPA102.total_instances += 1

                self.data_pin = int(data_pin)
                self.clock_pin = int(clock_pin)
                self.led_count = int(led_count)

                self._setup_complete = False

            # region Setup
            def setup(self) -> None:
                """Send APA102 configuration commands to the device."""
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDAPA102: GPIO_Lib transport not connected")
                
                if self.data_pin < 0 or self.data_pin > 0xFFFF:
                    raise ValueError("FastLEDAPA102: data_pin out of range")
                if self.clock_pin < 0 or self.clock_pin > 0xFFFF:
                    raise ValueError("FastLEDAPA102: clock_pin out of range")
                if self.led_count <= 0 or self.led_count > 0xFFFF:
                    raise ValueError("FastLEDAPA102: led_count out of range")

                # Create instance
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_APA102_CREATE, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                # Setup with all parameters
                payload = (
                    self.identifier.to_bytes(2, "little")
                    + self.gpio_lib._encode_pin(self.data_pin)
                    + self.gpio_lib._encode_pin(self.clock_pin)
                    + int(self.led_count).to_bytes(2, "little")
                )
                packet = self.gpio_lib._build_packet(CMD_APA102_SETUP, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                self._setup_complete = True
            
            # region Send LED data
            def send_led_data(self, led_data: list[tuple[int, int, int]]) -> None:
                """Send LED data to the device for updating the LED strip."""
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDAPA102: GPIO_Lib transport not connected")

                if not self._setup_complete:
                    self.setup()

                if len(led_data) != self.led_count:
                    raise ValueError("FastLEDAPA102: led_data length does not match number of LEDs")
                
                # Prepare LED data bytes (RGB format)
                led_bytes = bytearray()
                for r, g, b in led_data:
                    if r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
                        raise ValueError("FastLEDAPA102: LED color values must be in range 0-255")
                    led_bytes.extend(bytes([r & 0xFF, g & 0xFF, b & 0xFF]))

                # Send LED data
                payload = self.identifier.to_bytes(2, "little") + led_bytes
                packet = self.gpio_lib._build_packet(CMD_APA102_SHOW, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            
            # region Set Brightness 
            def set_brightness(self, brightness: int) -> None:
                """Set the brightness for the LED strip (0-255)."""
                if brightness < 0 or brightness > 255:
                    raise ValueError("FastLEDAPA102: brightness must be in range 0-255")
                
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDAPA102: GPIO_Lib transport not connected")

                if not self._setup_complete:
                    self.setup()

                payload = self.identifier.to_bytes(2, "little") + bytes([brightness & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_APA102_SET_BRIGHTNESS, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        # region WS2812
        class FastLEDWS2812:
            """WS2812 (NeoPixel) LED strip handler - requires data pin only."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                data_pin: int,
                led_count: int,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.FastLED.FastLEDWS2812.total_instances
                gpio_lib.FastLED.FastLEDWS2812.total_instances += 1

                self.data_pin = int(data_pin)
                self.led_count = int(led_count)

                self._setup_complete = False

            # region Setup
            def setup(self) -> None:
                """Send WS2812 configuration commands to the device."""
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDWS2812: GPIO_Lib transport not connected")
                
                if self.data_pin < 0 or self.data_pin > 0xFFFF:
                    raise ValueError("FastLEDWS2812: data_pin out of range")
                if self.led_count <= 0 or self.led_count > 0xFFFF:
                    raise ValueError("FastLEDWS2812: led_count out of range")

                # Create instance
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_WS2812_CREATE, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                # Setup with all parameters
                payload = (
                    self.identifier.to_bytes(2, "little")
                    + self.gpio_lib._encode_pin(self.data_pin)
                    + int(self.led_count).to_bytes(2, "little")
                )
                packet = self.gpio_lib._build_packet(CMD_WS2812_SETUP, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                self._setup_complete = True


            # region Send LED data
            def send_led_data(self, led_data: list[tuple[int, int, int]]) -> None:
                """Send LED data to the device for updating the LED strip."""
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDWS2812: GPIO_Lib transport not connected")

                if not self._setup_complete:
                    self.setup()

                if len(led_data) != self.led_count:
                    raise ValueError("FastLEDWS2812: led_data length does not match number of LEDs")
                
                # Prepare LED data bytes (RGB format)
                led_bytes = bytearray()
                for r, g, b in led_data:
                    if r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
                        raise ValueError("FastLEDWS2812: LED color values must be in range 0-255")
                    led_bytes.extend(bytes([r & 0xFF, g & 0xFF, b & 0xFF]))

                # Send LED data
                payload = self.identifier.to_bytes(2, "little") + led_bytes
                packet = self.gpio_lib._build_packet(CMD_WS2812_SHOW, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            

            # region Set Brightness
            def set_brightness(self, brightness: int) -> None:
                """Set the brightness for the LED strip (0-255)."""
                if brightness < 0 or brightness > 255:
                    raise ValueError("FastLEDWS2812: brightness must be in range 0-255")
                
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("FastLEDWS2812: GPIO_Lib transport not connected")

                if not self._setup_complete:
                    self.setup()

                payload = self.identifier.to_bytes(2, "little") + bytes([brightness & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_WS2812_SET_BRIGHTNESS, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)


    class UART:
        """UART peripheral handler."""
        total_instances = 0

        def __init__(
            self,
            gpio_lib: GPIO_Lib,
            tx_pin: int,
            rx_pin: int,
            baudrate: int = 115200,
            data_bits: int = 8,
            parity: UARTParity = UARTParity.NONE,
            stop_bits: int = 1,
            flow_control: UARTFlowControl = UARTFlowControl.NONE,
        ) -> None:
            self.gpio_lib = gpio_lib
            self.identifier = gpio_lib.UART.total_instances
            gpio_lib.UART.total_instances += 1

            self.tx_pin = int(tx_pin)
            self.rx_pin = int(rx_pin)
            self.baudrate = int(baudrate)
            self.data_bits = int(data_bits)
            self.parity = UARTParity(parity)
            self.stop_bits = int(stop_bits)
            self.flow_control = UARTFlowControl(flow_control)

            self._setup_complete = False

        def setup(self) -> None:
            if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                raise RuntimeError("UART: GPIO_Lib transport not connected")
            if self.tx_pin < 0 or self.tx_pin > 0xFFFF:
                raise ValueError("UART: tx_pin out of range")
            if self.rx_pin < 0 or self.rx_pin > 0xFFFF:
                raise ValueError("UART: rx_pin out of range")

            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_CREATE, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.tx_pin)
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_PIN_TX, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.rx_pin)
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_PIN_RX, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + int(self.baudrate).to_bytes(4, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_BAUDRATE, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + bytes([self.data_bits & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_DATA_BITS, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + bytes([self.parity.value & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_PARITY, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + bytes([self.stop_bits & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_STOPBITS, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + bytes([self.flow_control.value & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_UART_SET_FLOWCONTROL, payload), wait_ack=False)

            self._setup_complete = True

        def write(self, data: bytes | bytearray) -> None:
            if not self._setup_complete:
                self.setup()
            if not isinstance(data, (bytes, bytearray)):
                raise ValueError("UART: data must be bytes-like")
            payload = self.identifier.to_bytes(2, "little") + bytes(data)
            packet = self.gpio_lib._build_packet(CMD_UART_WRITE, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        def read(self, length: int, timeout: float = 1.0) -> bytes:
            if not self._setup_complete:
                self.setup()
            if length <= 0 or length > 0xFFFF:
                raise ValueError("UART: length out of range")
            payload = self.identifier.to_bytes(2, "little") + int(length).to_bytes(2, "little")
            packet = self.gpio_lib._build_packet(CMD_UART_READ, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            return self.gpio_lib._await_response(CMD_UART_READ, self.identifier, timeout=timeout)


    class I2C:
        """I2C peripheral handler."""
        total_instances = 0

        def __init__(
            self,
            gpio_lib: GPIO_Lib,
            clock_pin: int = -1,
            data_pin: int = -1,
            frequency: int = 400_000,
            i2c_bus: int = 0,
        ) -> None:
            self.gpio_lib = gpio_lib
            self.identifier = gpio_lib.I2C.total_instances
            gpio_lib.I2C.total_instances += 1

            self.clock_pin = int(clock_pin)
            self.data_pin = int(data_pin)
            self.frequency = int(frequency)
            self.i2c_bus = int(i2c_bus)

            if self.i2c_bus not in (0, 1):
                raise ValueError("I2C: i2c_bus must be 0 (Wire) or 1 (Wire1)")

            self._setup_complete = False

        def setup(self) -> None:
            if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                raise RuntimeError("I2C: GPIO_Lib transport not connected")

            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_I2C_CREATE, payload), wait_ack=False)

            # Send I2C bus selection (Wire=0, Wire1=1)
            payload = self.identifier.to_bytes(2, "little") + bytes([self.i2c_bus & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_I2C_SET_BUS, payload), wait_ack=False)

            # Only send pin configuration if pins are explicitly provided
            if self.clock_pin >= 0:
                payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.clock_pin)
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_I2C_SET_PIN_CLOCK, payload), wait_ack=False)

            if self.data_pin >= 0:
                payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.data_pin)
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_I2C_SET_PIN_DATA, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + int(self.frequency).to_bytes(4, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_I2C_SET_FREQUENCY, payload), wait_ack=False)

            self._setup_complete = True

        def write(self, address: int, data: bytes | bytearray) -> None:
            if not self._setup_complete:
                self.setup()
            if address < 0 or address > 0x7F:
                raise ValueError("I2C: address out of range")
            if not isinstance(data, (bytes, bytearray)):
                raise ValueError("I2C: data must be bytes-like")
            payload = self.identifier.to_bytes(2, "little") + bytes([address & 0x7F]) + bytes(data)
            packet = self.gpio_lib._build_packet(CMD_I2C_WRITE, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        def read(self, address: int, length: int, timeout: float = 1.0) -> bytes:
            if not self._setup_complete:
                self.setup()
            if address < 0 or address > 0x7F:
                raise ValueError("I2C: address out of range")
            if length <= 0 or length > 0xFFFF:
                raise ValueError("I2C: length out of range")
            payload = self.identifier.to_bytes(2, "little") + bytes([address & 0x7F]) + int(length).to_bytes(2, "little")
            packet = self.gpio_lib._build_packet(CMD_I2C_READ, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            return self.gpio_lib._await_response(CMD_I2C_READ, self.identifier, timeout=timeout)

        def write_read(
            self,
            address: int,
            write_data: bytes | bytearray,
            read_length: int,
            timeout: float = 1.0,
        ) -> bytes:
            if not self._setup_complete:
                self.setup()
            if address < 0 or address > 0x7F:
                raise ValueError("I2C: address out of range")
            if read_length <= 0 or read_length > 0xFFFF:
                raise ValueError("I2C: read_length out of range")
            if not isinstance(write_data, (bytes, bytearray)):
                raise ValueError("I2C: write_data must be bytes-like")
            write_len = len(write_data)
            payload = (
                self.identifier.to_bytes(2, "little")
                + bytes([address & 0x7F])
                + int(write_len).to_bytes(2, "little")
                + bytes(write_data)
                + int(read_length).to_bytes(2, "little")
            )
            packet = self.gpio_lib._build_packet(CMD_I2C_WRITE_READ, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            return self.gpio_lib._await_response(CMD_I2C_WRITE_READ, self.identifier, timeout=timeout)

        def full_address_scan(self, timeout: float = 2.0) -> List[int]:
            if not self._setup_complete:
                self.setup()
            payload = self.identifier.to_bytes(2, "little")
            packet = self.gpio_lib._build_packet(CMD_I2C_FULL_ADDRESS_SCAN, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            resp = self.gpio_lib._await_response(CMD_I2C_FULL_ADDRESS_SCAN, self.identifier, timeout=timeout)
            return list(resp)


    class SPI:
        """SPI peripheral handler."""
        total_instances = 0

        def __init__(
            self,
            gpio_lib: GPIO_Lib,
            data_pin: int,
            clock_pin: int,
            miso_pin: Optional[int] = None,
            frequency: int = 40_000_000,
            mode: SPIMode = SPIMode.MODE0,
        ) -> None:
            self.gpio_lib = gpio_lib
            self.identifier = gpio_lib.SPI.total_instances
            gpio_lib.SPI.total_instances += 1

            self.data_pin = int(data_pin)
            self.clock_pin = int(clock_pin)
            self.miso_pin = int(miso_pin) if miso_pin is not None else None
            self.frequency = int(frequency)
            self.mode = SPIMode(mode)

            self._setup_complete = False

        def setup(self) -> None:
            if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                raise RuntimeError("SPI: GPIO_Lib transport not connected")
            if self.data_pin < 0 or self.data_pin > 0xFFFF:
                raise ValueError("SPI: data_pin out of range")
            if self.clock_pin < 0 or self.clock_pin > 0xFFFF:
                raise ValueError("SPI: clock_pin out of range")

            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_CREATE, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.clock_pin)
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_SET_PIN_CLOCK, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.data_pin)
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_SET_PIN_MOSI, payload), wait_ack=False)

            if self.miso_pin is not None:
                payload = self.identifier.to_bytes(2, "little") + self.gpio_lib._encode_pin(self.miso_pin)
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_SET_PIN_MISO, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + int(self.frequency).to_bytes(4, "little")
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_SET_FREQUENCY, payload), wait_ack=False)

            payload = self.identifier.to_bytes(2, "little") + bytes([self.mode.value & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SPI_SET_MODE, payload), wait_ack=False)

            self._setup_complete = True

        def write(self, data: bytes | bytearray) -> None:
            if not self._setup_complete:
                self.setup()
            if not isinstance(data, (bytes, bytearray)):
                raise ValueError("SPI: data must be bytes-like")
            payload = self.identifier.to_bytes(2, "little") + bytes(data)
            packet = self.gpio_lib._build_packet(CMD_SPI_WRITE, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        def transfer(self, data: bytes | bytearray, timeout: float = 1.0) -> bytes:
            if not self._setup_complete:
                self.setup()
            if not isinstance(data, (bytes, bytearray)):
                raise ValueError("SPI: data must be bytes-like")
            payload = self.identifier.to_bytes(2, "little") + bytes(data)
            packet = self.gpio_lib._build_packet(CMD_SPI_READ, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            return self.gpio_lib._await_response(CMD_SPI_READ, self.identifier, timeout=timeout)


    class Display:
        """Display type namespace (ST7735, HD44780, AiP31068L, SSD1306)."""

        class DisplayST7735:
            """ST7735 LCD display handler (SPI)."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                spi: GPIO_Lib.SPI,
                cs_pin: int,
                rs_pin: int,
                enable_pin: int,
                backlight_pin: Optional[int] = None,
                backlight_inverted: bool = False,
                width: int = 80,
                height: int = 160,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.Display.DisplayST7735.total_instances
                gpio_lib.Display.DisplayST7735.total_instances += 1

                self.spi = spi
                self.cs_pin = int(cs_pin)
                self.rs_pin = int(rs_pin)
                self.enable_pin = int(enable_pin)
                self.backlight_pin = int(backlight_pin) if backlight_pin is not None else None
                self.backlight_inverted = bool(backlight_inverted)
                self.width = int(width)
                self.height = int(height)

                self._setup_complete = False

            def setup(self) -> None:
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("DisplayST7735: GPIO_Lib transport not connected")
                if self.width <= 0 or self.width > 0xFFFF or self.height <= 0 or self.height > 0xFFFF:
                    raise ValueError("DisplayST7735: width/height out of range")
                for pin_name, pin in ("cs_pin", self.cs_pin), ("rs_pin", self.rs_pin), ("enable_pin", self.enable_pin):
                    if pin < 0 or pin > 0xFF:
                        raise ValueError(f"DisplayST7735: {pin_name} out of range (0-255)")
                if self.backlight_pin is not None and (self.backlight_pin < 0 or self.backlight_pin > 0xFF):
                    raise ValueError("DisplayST7735: backlight_pin out of range (0-255)")

                if not self.spi._setup_complete:
                    self.spi.setup()

                payload = self.identifier.to_bytes(2, "little")
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_ST7735_CREATE, payload), wait_ack=False)

                payload = (
                    self.identifier.to_bytes(2, "little")
                    + int(self.width).to_bytes(2, "little")
                    + int(self.height).to_bytes(2, "little")
                    + int(self.spi.identifier).to_bytes(2, "little")
                    + bytes([self.cs_pin & 0xFF, self.rs_pin & 0xFF, self.enable_pin & 0xFF])
                )
                if self.backlight_pin is not None:
                    payload += bytes([self.backlight_pin & 0xFF, 1 if self.backlight_inverted else 0])
                packet = self.gpio_lib._build_packet(CMD_ST7735_SETUP_SPI, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                self._setup_complete = True

            def set_backlight(self, brightness: bool | int) -> None:
                if not self._setup_complete:
                    self.setup()
                if self.backlight_pin is None:
                    raise RuntimeError("DisplayST7735: backlight_pin not configured")

                if isinstance(brightness, bool):
                    level = 255 if brightness else 0
                else:
                    level = int(brightness)
                    if level < 0 or level > 255:
                        raise ValueError("DisplayST7735: brightness must be 0-255")

                payload = self.identifier.to_bytes(2, "little") + bytes([level & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_ST7735_SET_BACKLIGHT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_rotation(self, rotation: int) -> None:
                if not self._setup_complete:
                    self.setup()
                rot = int(rotation)
                if rot < 0 or rot > 3:
                    raise ValueError("DisplayST7735: rotation must be 0-3")
                payload = self.identifier.to_bytes(2, "little") + bytes([rot & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_ST7735_SET_ROTATION, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def clear(self) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_ST7735_CLEAR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_cursor(self, x: int, y: int) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little") + int(x).to_bytes(2, "little") + int(y).to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_ST7735_SET_CURSOR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text(self, text: str, x: Optional[int] = None, y: Optional[int] = None) -> None:
                if not self._setup_complete:
                    self.setup()
                # Only set cursor if coordinates are explicitly provided
                if x is not None or y is not None:
                    cursor_x = x if x is not None else 0
                    cursor_y = y if y is not None else 0
                    self.set_cursor(cursor_x, cursor_y)
                payload = self.identifier.to_bytes(2, "little") + text.encode(errors="replace")
                packet = self.gpio_lib._build_packet(CMD_ST7735_WRITE_TEXT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text_center(self, text: str) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little") + text.encode(errors="replace")
                packet = self.gpio_lib._build_packet(CMD_ST7735_WRITE_TEXT_CENTER, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_bitmap(self, bitmap_data: bytes | bytearray | List[int], x: int, y: int, width: int, height: int, random_rows: bool = False) -> None:
                if not self._setup_complete:
                    self.setup()
                if width <= 0 or height <= 0:
                    raise ValueError("DisplayST7735: bitmap size must be positive")

                bitmap_bytes = None
                if isinstance(bitmap_data, (bytes, bytearray)):
                    bitmap_bytes = bitmap_data
                elif isinstance(bitmap_data, list):
                    try:
                        bitmap_bytes = bytes(bitmap_data)
                    except ValueError:
                        try:
                            bitmap_bytes = b""
                            for pixel in bitmap_data:
                                bitmap_bytes += bytes([pixel & 0xFF, (pixel >> 8) & 0xFF])
                        except Exception as e:
                            raise ValueError(
                                "DisplayST7735: unable to convert bitmap data. Expected raw bytes or RGB565 16-bit list"
                            ) from e

                if bitmap_bytes is None:
                    raise ValueError("DisplayST7735: bitmap_data must be bytes, bytearray, or list")

                bitmap_view = memoryview(bitmap_bytes)
                expected = int(width) * int(height) * 2
                if len(bitmap_view) != expected:
                    raise ValueError(f"DisplayST7735: bitmap_data length must be {expected} bytes for RGB565")
                # Convert on host: RGB565 (LE bytes) -> BGR565 then invert bits (MCU no longer performs this).
                conv = bytearray(expected)
                for i in range(0, expected, 2):
                    rgb565 = bitmap_view[i] | (bitmap_view[i + 1] << 8)
                    r = (rgb565 >> 11) & 0x1F
                    g = (rgb565 >> 5) & 0x3F
                    b = rgb565 & 0x1F
                    bgr565 = (b << 11) | (g << 5) | r
                    pix = bgr565 ^ 0xFFFF
                    conv[i] = pix & 0xFF
                    conv[i + 1] = (pix >> 8) & 0xFF
                bitmap_view = memoryview(conv)
                x = int(x)
                y = int(y)
                w = int(width)
                h = int(height)
                begin_payload = (
                    self.identifier.to_bytes(2, "little")
                    + bytes([1])
                    + x.to_bytes(2, "little")
                    + y.to_bytes(2, "little")
                    + w.to_bytes(2, "little")
                    + h.to_bytes(2, "little")
                )
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_ST7735_WRITE_BITMAP, begin_payload),
                    wait_ack=True,
                    validate=False,
                )

                row_len = w * 2
                if random_rows:
                    import random
                    row_indices = list(range(h))
                    random.shuffle(row_indices)
                else:
                    row_indices = range(h)
                id_bytes = self.identifier.to_bytes(2, "little")
                for row_idx in row_indices:
                    start = row_idx * row_len
                    end = start + row_len
                    row_view = bitmap_view[start:end]
                    row_payload = id_bytes + bytes([2]) + int(row_idx).to_bytes(2, "little") + row_view.tobytes()
                    packet = self.gpio_lib._build_packet(CMD_ST7735_WRITE_BITMAP, row_payload)
                    self.gpio_lib.log_debug_message(f"Packet size for row {row_idx}: {len(packet)} bytes")
                    self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False, validate=False)

                end_payload = self.identifier.to_bytes(2, "little") + bytes([3])
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_ST7735_WRITE_BITMAP, end_payload),
                    wait_ack=True,
                    validate=False,
                )

        class DisplayHD44780:
            """HD44780 character LCD handler (I2C via backpack)."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                i2c: GPIO_Lib.I2C,
                address: int,
                cols: int = 16,
                rows: int = 2,
                backlight: bool = True,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.Display.DisplayHD44780.total_instances
                gpio_lib.Display.DisplayHD44780.total_instances += 1

                self.i2c = i2c
                self.address = int(address)
                self.cols = int(cols)
                self.rows = int(rows)
                self.backlight = bool(backlight)

                self._setup_complete = False

            def setup(self) -> None:
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("DisplayHD44780: GPIO_Lib transport not connected")
                if self.address < 0 or self.address > 0x7F:
                    raise ValueError("DisplayHD44780: I2C address out of range")
                if self.cols <= 0 or self.cols > 0xFFFF or self.rows <= 0 or self.rows > 0xFFFF:
                    raise ValueError("DisplayHD44780: cols/rows out of range")

                if not self.i2c._setup_complete:
                    self.i2c.setup()

                payload = self.identifier.to_bytes(2, "little")
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_HD44780_CREATE, payload), wait_ack=False)

                payload = (
                    self.identifier.to_bytes(2, "little")
                    + int(self.cols).to_bytes(2, "little")
                    + int(self.rows).to_bytes(2, "little")
                    + int(self.i2c.identifier).to_bytes(2, "little")
                    + bytes([self.address & 0x7F])
                )
                packet = self.gpio_lib._build_packet(CMD_HD44780_SETUP_I2C, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                self._setup_complete = True
                if self.backlight:
                    self.set_backlight(True)

            def clear(self) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_HD44780_CLEAR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_cursor(self, col: int, row: int) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little") + int(col).to_bytes(2, "little") + int(row).to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_HD44780_SET_CURSOR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text(self, text: str, col: Optional[int] = None, row: Optional[int] = None) -> None:
                if not self._setup_complete:
                    self.setup()
                # Only set cursor if coordinates are explicitly provided
                if col is not None or row is not None:
                    cursor_col = col if col is not None else 0
                    cursor_row = row if row is not None else 0
                    self.set_cursor(cursor_col, cursor_row)
                payload = self.identifier.to_bytes(2, "little") + text.encode(errors="replace")
                packet = self.gpio_lib._build_packet(CMD_HD44780_WRITE_TEXT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_backlight(self, brightness: bool | int) -> None:
                if not self._setup_complete:
                    self.setup()
                if isinstance(brightness, bool):
                    level = 255 if brightness else 0
                else:
                    level = int(brightness)
                    if level < 0 or level > 255:
                        raise ValueError("DisplayHD44780: brightness must be 0-255")
                payload = self.identifier.to_bytes(2, "little") + bytes([level & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_HD44780_SET_BACKLIGHT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        class DisplayAiP31068L:
            """AiP31068L character LCD handler (I2C)."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                i2c: GPIO_Lib.I2C,
                address: int,
                cols: int = 16,
                rows: int = 2,
                backlight: bool = True,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.Display.DisplayAiP31068L.total_instances
                gpio_lib.Display.DisplayAiP31068L.total_instances += 1

                self.i2c = i2c
                self.address = int(address)
                self.cols = int(cols)
                self.rows = int(rows)
                self.backlight = bool(backlight)

                self._setup_complete = False

            def setup(self) -> None:
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("DisplayAiP31068L: GPIO_Lib transport not connected")
                if self.address < 0 or self.address > 0x7F:
                    raise ValueError("DisplayAiP31068L: I2C address out of range")
                if self.cols <= 0 or self.cols > 0xFFFF or self.rows <= 0 or self.rows > 0xFFFF:
                    raise ValueError("DisplayAiP31068L: cols/rows out of range")

                if not self.i2c._setup_complete:
                    self.i2c.setup()

                payload = self.identifier.to_bytes(2, "little")
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_AIP31068L_CREATE, payload), wait_ack=False)

                payload = (
                    self.identifier.to_bytes(2, "little")
                    + int(self.cols).to_bytes(2, "little")
                    + int(self.rows).to_bytes(2, "little")
                    + int(self.i2c.identifier).to_bytes(2, "little")
                    + bytes([self.address & 0x7F])
                )
                packet = self.gpio_lib._build_packet(CMD_AIP31068L_SETUP_I2C, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

                self._setup_complete = True
                if self.backlight:
                    self.set_backlight(True)

            def clear(self) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_AIP31068L_CLEAR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_cursor(self, col: int, row: int) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little") + int(col).to_bytes(2, "little") + int(row).to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_AIP31068L_SET_CURSOR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text(self, text: str, col: Optional[int] = None, row: Optional[int] = None) -> None:
                if not self._setup_complete:
                    self.setup()
                # Only set cursor if coordinates are explicitly provided
                if col is not None or row is not None:
                    cursor_col = col if col is not None else 0
                    cursor_row = row if row is not None else 0
                    self.set_cursor(cursor_col, cursor_row)
                payload = self.identifier.to_bytes(2, "little") + text.encode(errors="replace")
                packet = self.gpio_lib._build_packet(CMD_AIP31068L_WRITE_TEXT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_backlight(self, brightness: bool | int) -> None:
                if not self._setup_complete:
                    self.setup()
                if isinstance(brightness, bool):
                    level = 255 if brightness else 0
                else:
                    level = int(brightness)
                    if level < 0 or level > 255:
                        raise ValueError("DisplayAiP31068L: brightness must be 0-255")
                payload = self.identifier.to_bytes(2, "little") + bytes([level & 0xFF])
                packet = self.gpio_lib._build_packet(CMD_AIP31068L_SET_BACKLIGHT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

        class DisplaySSD1306:
            """SSD1306 OLED display handler (I2C or SPI)."""
            total_instances = 0

            def __init__(
                self,
                gpio_lib: GPIO_Lib,
                width: int = 128,
                height: int = 64,
                i2c: Optional[GPIO_Lib.I2C] = None,
                spi: Optional[GPIO_Lib.SPI] = None,
                address: int = 0x3C,
                cs_pin: Optional[int] = None,
                dc_pin: Optional[int] = None,
                reset_pin: Optional[int] = None,
            ) -> None:
                self.gpio_lib = gpio_lib
                self.identifier = gpio_lib.Display.DisplaySSD1306.total_instances
                gpio_lib.Display.DisplaySSD1306.total_instances += 1

                self.width = int(width)
                self.height = int(height)
                self.i2c = i2c
                self.spi = spi
                self.address = int(address)
                self.cs_pin = int(cs_pin) if cs_pin is not None else None
                self.dc_pin = int(dc_pin) if dc_pin is not None else None
                self.reset_pin = int(reset_pin) if reset_pin is not None else None

                self._setup_complete = False

            def setup(self) -> None:
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("DisplaySSD1306: GPIO_Lib transport not connected")
                if self.width <= 0 or self.width > 0xFFFF or self.height <= 0 or self.height > 0xFFFF:
                    raise ValueError("DisplaySSD1306: width/height out of range")

                payload = self.identifier.to_bytes(2, "little")
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_SSD1306_CREATE, payload), wait_ack=False)

                if self.i2c is not None:
                    if not self.i2c._setup_complete:
                        self.i2c.setup()
                    if self.address < 0 or self.address > 0x7F:
                        raise ValueError("DisplaySSD1306: I2C address out of range")

                    payload = (
                        self.identifier.to_bytes(2, "little")
                        + int(self.width).to_bytes(2, "little")
                        + int(self.height).to_bytes(2, "little")
                        + int(self.i2c.identifier).to_bytes(2, "little")
                        + bytes([self.address & 0x7F])
                    )
                    packet = self.gpio_lib._build_packet(CMD_SSD1306_SETUP_I2C, payload)
                    self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
                elif self.spi is not None:
                    if not self.spi._setup_complete:
                        self.spi.setup()
                    if self.cs_pin is None or self.dc_pin is None:
                        raise ValueError("DisplaySSD1306: cs_pin and dc_pin required for SPI")
                    rst_pin = self.reset_pin if self.reset_pin is not None else 0xFF
                    payload = (
                        self.identifier.to_bytes(2, "little")
                        + int(self.width).to_bytes(2, "little")
                        + int(self.height).to_bytes(2, "little")
                        + int(self.spi.identifier).to_bytes(2, "little")
                        + bytes([self.cs_pin & 0xFF, self.dc_pin & 0xFF, rst_pin & 0xFF])
                    )
                    packet = self.gpio_lib._build_packet(CMD_SSD1306_SETUP_SPI, payload)
                    self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
                else:
                    raise ValueError("DisplaySSD1306: either i2c or spi must be provided")

                self._setup_complete = True

            def clear(self) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_SSD1306_CLEAR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_cursor(self, x: int, y: int) -> None:
                if not self._setup_complete:
                    self.setup()
                payload = self.identifier.to_bytes(2, "little") + int(x).to_bytes(2, "little") + int(y).to_bytes(2, "little")
                packet = self.gpio_lib._build_packet(CMD_SSD1306_SET_CURSOR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text(self, text: str, x: Optional[int] = None, y: Optional[int] = None) -> None:
                if not self._setup_complete:
                    self.setup()
                # Only set cursor if coordinates are explicitly provided
                if x is not None or y is not None:
                    cursor_x = x if x is not None else 0
                    cursor_y = y if y is not None else 0
                    self.set_cursor(cursor_x, cursor_y)
                payload = self.identifier.to_bytes(2, "little") + text.encode(errors="replace")
                packet = self.gpio_lib._build_packet(CMD_SSD1306_WRITE_TEXT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_rotation(self, rotation: int) -> None:
                if not self._setup_complete:
                    self.setup()
                rot = int(rotation)
                if rot < 0 or rot > 3:
                    raise ValueError("DisplaySSD1306: rotation must be 0-3")
                payload = self.identifier.to_bytes(2, "little") + bytes([rot])
                packet = self.gpio_lib._build_packet(CMD_SSD1306_SET_ROTATION, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_brightness(self, level: int) -> None:
                """Set the display brightness (0=off, 255=full)."""
                if not self._setup_complete:
                    self.setup()
                brightness = int(level)
                if brightness < 0 or brightness > 255:
                    raise ValueError("DisplaySSD1306: brightness must be 0-255")
                payload = self.identifier.to_bytes(2, "little") + bytes([brightness])
                packet = self.gpio_lib._build_packet(CMD_SSD1306_SET_BRIGHTNESS, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_bitmap_mono(
                self,
                bitmap_data: bytes | bytearray | List[int],
                width: int,
                height: int,
                x: int = 0,
                y: int = 0,
                random_rows: bool = False,
            ) -> None:
                """Draw a monochrome bitmap at (x, y) with optional random row order."""
                if not self._setup_complete:
                    self.setup()
                if width <= 0 or height <= 0:
                    raise ValueError("DisplaySSD1306: bitmap size must be positive")

                expected_bytes = (int(width) * int(height) + 7) // 8
                bitmap_bytes = None
                if isinstance(bitmap_data, (bytes, bytearray)):
                    bitmap_bytes = bitmap_data
                elif isinstance(bitmap_data, list):
                    try:
                        bitmap_bytes = bytes(bitmap_data)
                    except ValueError:
                        bitmap_bytes = None

                    if bitmap_bytes is not None and len(bitmap_bytes) == int(width) * int(height):
                        packed = bytearray(expected_bytes)
                        for idx, val in enumerate(bitmap_bytes):
                            if val:
                                packed[idx // 8] |= (1 << (idx % 8))
                        bitmap_bytes = bytes(packed)

                if bitmap_bytes is None:
                    raise ValueError("DisplaySSD1306: bitmap_data must be bytes, bytearray, or list")
                if len(bitmap_bytes) != expected_bytes:
                    raise ValueError(f"DisplaySSD1306: bitmap_data length must be {expected_bytes} bytes for monochrome")

                w = int(width)
                h = int(height)
                row_bytes = (w + 7) // 8

                begin_payload = (
                    self.identifier.to_bytes(2, "little")
                    + bytes([1])
                    + int(x).to_bytes(2, "little")
                    + int(y).to_bytes(2, "little")
                    + w.to_bytes(2, "little")
                    + h.to_bytes(2, "little")
                )
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_SSD1306_WRITE_BITMAP, begin_payload),
                    wait_ack=True,
                    validate=False,
                )

                if random_rows:
                    import random
                    row_indices = list(range(h))
                    random.shuffle(row_indices)
                else:
                    row_indices = range(h)

                id_bytes = self.identifier.to_bytes(2, "little")
                for row_idx in row_indices:
                    start = row_idx * row_bytes
                    end = start + row_bytes
                    row_view = bitmap_bytes[start:end]
                    row_payload = id_bytes + bytes([2]) + int(row_idx).to_bytes(2, "little") + bytes(row_view)
                    packet = self.gpio_lib._build_packet(CMD_SSD1306_WRITE_BITMAP, row_payload)
                    self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False, validate=False)

                end_payload = self.identifier.to_bytes(2, "little") + bytes([3])
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_SSD1306_WRITE_BITMAP, end_payload),
                    wait_ack=True,
                    validate=False,
                )

            def write_bitmap_rgb565(
                self,
                bitmap_data: bytes | bytearray | List[int],
                width: int,
                height: int,
                threshold: int = 128,
                x: int = 0,
                y: int = 0,
                random_rows: bool = False,
            ) -> None:
                if not self._setup_complete:
                    self.setup()
                if width <= 0 or height <= 0:
                    raise ValueError("DisplaySSD1306: bitmap size must be positive")
                expected = int(width) * int(height) * 2

                if isinstance(bitmap_data, list):
                    try:
                        raw = bytes(bitmap_data)
                        if len(raw) == expected:
                            bitmap_bytes = raw
                        else:
                            bitmap_bytes = b"".join(bytes([p & 0xFF, (p >> 8) & 0xFF]) for p in bitmap_data)
                    except ValueError:
                        bitmap_bytes = b"".join(bytes([p & 0xFF, (p >> 8) & 0xFF]) for p in bitmap_data)
                elif isinstance(bitmap_data, (bytes, bytearray)):
                    bitmap_bytes = bitmap_data
                else:
                    raise ValueError("DisplaySSD1306: bitmap_data must be bytes, bytearray, or list")

                if len(bitmap_bytes) != expected:
                    raise ValueError(f"DisplaySSD1306: bitmap_data length must be {expected} bytes for RGB565")

                mono_bytes = bytearray((int(width) * int(height) + 7) // 8)
                for i in range(0, len(bitmap_bytes), 2):
                    rgb565 = bitmap_bytes[i] | (bitmap_bytes[i + 1] << 8)
                    r = (rgb565 >> 11) & 0x1F
                    g = (rgb565 >> 5) & 0x3F
                    b = rgb565 & 0x1F
                    lum = (r * 255 // 31) * 0.299 + (g * 255 // 63) * 0.587 + (b * 255 // 31) * 0.114
                    idx = i // 2
                    if lum >= threshold:
                        mono_bytes[idx // 8] |= (1 << (idx % 8))

                self.write_bitmap_mono(bytes(mono_bytes), width=width, height=height, x=x, y=y, random_rows=random_rows)




























































    # [ ] TODO subclasses for peripherals. API call: GPIO_Lib.gpio.pin_mode() etc.


    # --- configuration (Arduino-like API) ------------------------

    def _encode_pin(self, p: int) -> bytes:
        if p < 0 or p > 0xFFFF:
            raise ValueError("pin out of range")
        if p <= 0xFF:
            return bytes([p & 0xFF])
        return bytes([p & 0xFF, (p >> 8) & 0xFF])

    def pinMode(self, pin: int | str, mode: PinMode, name: Optional[str] = None) -> None:
        """Configure `pin` with `mode` and optional `name`.

        mode: PinMode class:
            INPUT
            OUTPUT
            INPUT_PULLUP
            INPUT_PULLDOWN
            ANALOG_INPUT
            ANALOG_OUTPUT

        If `pin` is a string name, a numeric pin must be provided via `name`
        mapping elsewhere; prefer numeric pin values.
        """
        if isinstance(pin, str) and not pin.isnumeric():
            raise ValueError("pin_mode requires a numeric pin; use names only for read/write ops")
        pin_num = int(pin)
        if name:
            self.pin_to_name[pin_num] = name

        # update mirrors
        if mode == PinMode.OUTPUT:
            self.outputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_OUTPUT
            payload = self._encode_pin(pin_num)
        elif mode == PinMode.INPUT:
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT
            payload = self._encode_pin(pin_num)
        elif mode == PinMode.INPUT_PULLUP:
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT_PULLUP
            payload = self._encode_pin(pin_num)
        elif mode == PinMode.INPUT_PULLDOWN:
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT_PULLDOWN
            payload = self._encode_pin(pin_num)
        elif mode == PinMode.ANALOG_INPUT:
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "analog"})
            cmd = CMD_ANALOG_INPUT
            payload = self._encode_pin(pin_num)
        elif mode == PinMode.ANALOG_OUTPUT:
            self.outputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "analog"})
            cmd = CMD_ANALOG_OUTPUT
            payload = self._encode_pin(pin_num)
        else:
            raise ValueError(f"unknown mode: {mode}")

        # send packet if connected (enqueue for send worker)
        if self._transport and self._transport.is_connected:
            try:
                packet = self._build_packet(cmd, payload)
                self._add_packet_to_send_queue(packet, wait_ack=False)
            except Exception:
                if self.debug_enabled:
                    self.log_debug_message("pin_mode: enqueue failed")

    def attach_servo(self, pin: int, index: Optional[int] = None, name: Optional[str] = None) -> int:
        """Attach a servo to `pin`. Returns the servo index used."""
        pin_num = int(pin)
        if index is None:
            # choose next available index
            index = 0
            while index in self.servo_array:
                index += 1
        idx = int(index) & 0xFF
        self.servo_array[idx] = 0
        if name:
            self.pin_to_name[pin_num] = name
        payload = self._encode_pin(pin_num) + bytes([idx & 0xFF])
        if self._transport and self._transport.is_connected:
            try:
                packet = self._build_packet(CMD_SERVO_ATTACH, payload)
                self._add_packet_to_send_queue(packet, wait_ack=False)
            except Exception:
                if self.debug_enabled:
                    self.log_debug_message("attach_servo: enqueue failed")
        return idx

    def detach_servo(self, index: int) -> None:
        idx = int(index) & 0xFF
        if idx in self.servo_array:
            del self.servo_array[idx]
        try:
            if self._transport and self._transport.is_connected:
                packet = self._build_packet(CMD_SERVO_DETACH, bytes([idx & 0xFF]))
                self._add_packet_to_send_queue(packet, wait_ack=False)
        except Exception:
            if self.debug_enabled:
                self.log_debug_message("detach_servo: enqueue failed")

    # --- I/O methods ----------------------------------------------
    def digital_write(self, pin: int | str, val: bool = False) -> None:
        # resolve name and pin
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.outputs.get(name)
            if entry is None:
                raise ValueError(f"output name not found: {name}")
            pin_num = int(entry["pin"])
        else:
            pin_num = int(pin)
            name = self.pin_to_name.get(pin_num, str(pin_num))
            if name not in self.outputs:
                # create an ad-hoc output entry
                self.outputs[name] = {"pin": pin_num, "value": 0, "type": "digital"}
        v = 1 if val else 0
        self.outputs[name]["value"] = v
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_DIGITAL_WRITE
            # encode pin as 1 or 2 bytes
            def _encode_pin_local(p: int) -> bytes:
                if p <= 0xFF:
                    return bytes([p & 0xFF])
                return bytes([p & 0xFF, (p >> 8) & 0xFF])
            payload = _encode_pin_local(pin_num) + bytes([v & 0xFF])
            packet = self._build_packet(cmd, payload)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    def digital_read(self, pin: int | str) -> bool:
        if not self._transport or not self._transport.is_connected:
            return False
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.inputs.get(name)
            if entry is None:
                raise ValueError(f"input name not found: {name}")
            return bool(entry["value"])
        else:
            pin_num = int(pin)
            # Try name lookup first, then fall back to numeric string lookup
            name = self.pin_to_name.get(pin_num)
            if name and name in self.inputs:
                return bool(self.inputs[name]["value"])
            # Fall back to direct numeric key lookup
            str_key = str(pin_num)
            if str_key in self.inputs:
                return bool(self.inputs[str_key]["value"])
            # fallback: unknown pin
            return False

    def analog_write(self, pin: int | str, val: int) -> None:
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.outputs.get(name)
            if entry is None:
                raise ValueError(f"output name not found: {name}")
            pin_num = int(entry["pin"])
        else:
            pin_num = int(pin)
            name = self.pin_to_name.get(pin_num, str(pin_num))
            if name not in self.outputs:
                self.outputs[name] = {"pin": pin_num, "value": 0, "type": "analog"}
        self.outputs[name]["value"] = int(val)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_ANALOG_WRITE
            # encode pin and 16-bit value (little-endian)
            val_int = int(val)
            if pin_num <= 0xFF:
                payload = bytes([pin_num & 0xFF, val_int & 0xFF, (val_int >> 8) & 0xFF])
            else:
                payload = bytes([pin_num & 0xFF, (pin_num >> 8) & 0xFF, val_int & 0xFF, (val_int >> 8) & 0xFF])
            packet = self._build_packet(cmd, payload)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    def analog_read(self, pin: int | str) -> int:
        if not self._transport or not self._transport.is_connected:
            return 0
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.inputs.get(name)
            if entry is None:
                raise ValueError(f"input name not found: {name}")
            return int(entry["value"])
        else:
            pin_num = int(pin)
            # Try name lookup first, then fall back to numeric string lookup
            name = self.pin_to_name.get(pin_num)
            if name and name in self.inputs:
                return int(self.inputs[name]["value"])
            # Fall back to direct numeric key lookup
            str_key = str(pin_num)
            if str_key in self.inputs:
                return int(self.inputs[str_key]["value"])
            return 0

    def set_analog_threshold(self, pin: int | str, threshold: int) -> None:
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.inputs.get(name)
            if entry is None:
                raise ValueError(f"input name not found: {name}")
            pin_num = int(entry["pin"])
        else:
            pin_num = int(pin)
        thresh = int(threshold) & 0xFF
        if pin_num <= 0xFF:
            payload = bytes([pin_num & 0xFF, thresh])
        else:
            payload = bytes([pin_num & 0xFF, (pin_num >> 8) & 0xFF, thresh])
        packet = self._build_packet(CMD_ANALOG_READ_TOLERANCE, payload)
        self._add_packet_to_send_queue(packet, wait_ack=False)

    def set_analog_read_resolution(self, bits: int) -> None:
        resolution_bits = int(bits) & 0xFF
        payload = bytes([resolution_bits])
        packet = self._build_packet(CMD_ANALOG_READ_RESOLUTION, payload)
        self._add_packet_to_send_queue(packet, wait_ack=False)

    def servo_write(self, index: int, val: int) -> None:
        self.servo_array[index] = int(val)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_SERVO_WRITE
            payload = bytes([index & 0xFF, int(val) & 0xFF])
            packet = self._build_packet(cmd, payload)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    def lcd_write(self, text: str, identifier: int = 0) -> None:
        # simple append model; device is expected to handle display payloads
        self.lcd_lines.append(text)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_ST7735_WRITE_TEXT
            b = int(identifier).to_bytes(2, "little") + text.encode(errors="replace")
            packet = self._build_packet(cmd, b)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    # --- sync -----------------------------------------------------
    def sync(self) -> None:
        """Push local outputs to device and pull immediate updates (requests)."""
        if not self._transport or not self._transport.is_connected:
            return
        # push outputs
        for name, entry in self.outputs.items():
            pin_idx = int(entry["pin"])
            val = int(entry["value"])
            if entry.get("type") == "analog":
                cmd = CMD_ANALOG_WRITE
                # analog uses 2 bytes for value
                if pin_idx <= 0xFF:
                    payload = bytes([pin_idx & 0xFF, val & 0xFF, (val >> 8) & 0xFF])
                else:
                    payload = bytes([pin_idx & 0xFF, (pin_idx >> 8) & 0xFF, val & 0xFF, (val >> 8) & 0xFF])
            else:
                cmd = CMD_DIGITAL_WRITE
                # digital uses 1 byte for value
                if pin_idx <= 0xFF:
                    payload = bytes([pin_idx & 0xFF, val & 0xFF])
                else:
                    payload = bytes([pin_idx & 0xFF, (pin_idx >> 8) & 0xFF, val & 0xFF])
            self._add_packet_to_send_queue(self._build_packet(cmd, payload), wait_ack=False)
            time.sleep(0.0005)
        # request reads for inputs: send P1 read requests (empty payload meaning 'give value')
        for name, entry in self.inputs.items():
            pin_idx = int(entry["pin"])
            if entry.get("type") == "analog":
                cmd = CMD_ANALOG_READ
            else:
                cmd = CMD_DIGITAL_READ
            # read requests: encode pin index as 1 or 2 bytes (no extra value)
            if pin_idx <= 0xFF:
                payload = bytes([pin_idx & 0xFF])
            else:
                payload = bytes([pin_idx & 0xFF, (pin_idx >> 8) & 0xFF])
            self._add_packet_to_send_queue(self._build_packet(cmd, payload), wait_ack=False)
            time.sleep(0.0005)

    # --- internals ------------------------------------------------

    def _record_response(self, cmd: int, identifier: int, payload: bytes) -> None:
        key = (int(cmd), int(identifier))
        with self._resp_cv:
            self._responses[key] = payload
            self._resp_cv.notify_all()

    def _await_response(self, cmd: int, identifier: int, timeout: float = 1.0) -> bytes:
        key = (int(cmd), int(identifier))
        end = time.time() + float(timeout)
        with self._resp_cv:
            while True:
                if key in self._responses:
                    return self._responses.pop(key)
                remaining = end - time.time()
                if remaining <= 0:
                    return b""
                self._resp_cv.wait(timeout=remaining)


    # region packet handling
    def _handle_packet(self, cmd: int, payload: bytes) -> None:
        """Handle incoming command frames (device -> host updates)."""
        
        # Helper to update pin state in dictionaries with caching
        def _update_pin(pin: int, val: int, pin_dict: dict, pin_type: str) -> str:
            """Update pin state in dictionary, return pin name."""
            name = self.pin_to_name.get(pin)
            if not name:
                name = str(pin)
            
            if name not in pin_dict:
                pin_dict[name] = {"pin": pin, "value": int(val), "type": pin_type}
            else:
                pin_dict[name]["value"] = int(val)
            return name
        
        # Device-level status: OK frame
        if cmd == CMD_DEVICE_OK:
            # increment counter, record timestamp, and wake waiters
            with self._ok_cv:
                self.debug_ok_received += 1
                now = datetime.now()
                # Keep bounded list to prevent memory leak in long-running processes
                if len(self._ok_timestamps) >= self._max_ok_timestamps:
                    self._ok_timestamps.pop(0)
                self._ok_timestamps.append(now)
                self._ok_cv.notify_all()
            
            # Log debug message if enabled
            self.log_debug_message(f"device: OK")
            return
        if cmd == CMD_DEVICE_ERROR:
            self.log_debug_message(f"device: ERROR {payload}. Last packet sent: {self.last_send_data}")
            # [ ] TODO maybe set an error state or raise an exception
            return

        # UART/I2C/SPI read responses: payload = id(2) + data
        if cmd in (CMD_UART_READ, CMD_I2C_READ, CMD_I2C_WRITE_READ, CMD_I2C_FULL_ADDRESS_SCAN, CMD_SPI_READ) and len(payload) >= 2:
            identifier = int(payload[0]) | (int(payload[1]) << 8)
            self._record_response(cmd, identifier, payload[2:])
            return

        # Digital read responses
        if cmd == CMD_DIGITAL_READ and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            _update_pin(pin, val, self.inputs, "digital")
            if self.debug_enabled:
                print(f"input update pin={pin} val={val}")
            return

        # Output updates (device echo)
        if cmd == CMD_DIGITAL_WRITE and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            _update_pin(pin, val, self.outputs, "digital")
            return

        # Analog read responses (16-bit value)
        if cmd == CMD_ANALOG_READ and len(payload) >= 3:
            pin, val = payload[0], payload[1] | (payload[2] << 8)
            _update_pin(pin, val, self.inputs, "analog")
            if self.debug_enabled:
                print(f"analog input update pin={pin} val={val}")
            return

        # Analog write echo/update (16-bit value)
        if cmd == CMD_ANALOG_WRITE and len(payload) >= 3:
            pin, val = payload[0], payload[1] | (payload[2] << 8)
            _update_pin(pin, val, self.outputs, "analog")
            return

        # Servo updates
        if cmd == CMD_SERVO_WRITE and len(payload) >= 2:
            idx_servo, val = payload[0], payload[1]
            self.servo_array[idx_servo] = int(val)
            return

        # ST7735 text
        if cmd == CMD_ST7735_WRITE_TEXT and len(payload) >= 3:
            try:
                text = payload[2:].decode(errors="replace")
            except Exception:
                text = ""
            self.lcd_lines.append(text)
            return
        
        # Firmeware Build Flags
        if cmd == CMD_FIRMWARE_BUILD_FLAGS:
            self.firmware_build_flags = payload.decode('utf-8', errors='replace').strip('\x00').strip().split(' ') if payload else []
            return

        # Firmware Name
        if cmd == CMD_FIRMWARE_NAME:
            try:
                name = payload.decode(errors="replace")
                self.firmware_name = name
            except Exception:
                self.log_debug_message(f"invalid firmware name payload: {payload}")
            return
        
        # Firmware version
        if cmd == CMD_FIRMWARE_VERSION:
            if len(payload) == 3:
                major = int(payload[0])
                minor = int(payload[1])
                patch = int(payload[2])
                self.firmware_version = (major, minor, patch)
            else:
                self.log_debug_message(f"invalid firmware version payload: {payload}")
            return

    def _name_to_pin(self, name: str) -> int:
        # resolve a configured name to its pin number
        if name in self.outputs:
            return int(self.outputs[name]["pin"])
        if name in self.inputs:
            return int(self.inputs[name]["pin"])
        # fallback: maybe the name is numeric
        try:
            return int(name)
        except Exception:
            raise ValueError(f"pin name not found: {name}")



__all__ = ["GPIO_Lib"]



