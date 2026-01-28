from __future__ import annotations

import os
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any

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
# ANALOG MAX command to set the max value for analog writes/reads in GPIO_Lib and on the device
CMD_ANALOG_MAX                      = 0x000A # Set analog max value, payload: (max value[e.g. 255 or 1023. depending on board ADC resolution]) 
CMD_ANALOG_TOLERANCE                = 0x000B # Set analog read tolerance, payload: (tolerance value[e.g. 4]) update only if change exceeds this value

# Command definitions for GPIO operations (0x001X)
CMD_DIGITAL_READ                    = 0x0010 # Digital read, payload: (pin number) , returns: (value)
CMD_DIGITAL_WRITE                   = 0x0011 # Digital write, payload: (pin number, value[0/1])
CMD_ANALOG_READ                     = 0x0012 # Analog read, payload: (pin number), returns: (value)
CMD_ANALOG_WRITE                    = 0x0013 # Analog write, payload: (pin number, value[0-analog max])

# region Display CMDs
# Command definitions for Display operations
# LCD commands (0x002X)
CMD_LCD_CREATE                      = 0x0020 # Create LCD instance, payload: (identifier[2 bytes])
CMD_LCD_SETUP_I2C                   = 0x0021 # Setup LCD I2C, payload: (identifier[2 bytes], width[2 byte], height[2 byte], i2c identifier[2 bytes], i2c address[1 byte])
CMD_LCD_SETUP_SPI                   = 0x0022 # Setup LCD SPI, payload: (identifier[2 bytes], width[2 byte], height[2 byte], spi identifier[2 bytes], cs pin[1 byte], rs pin[1 byte], enable pin[1 byte])
CMD_LCD_CLEAR                       = 0x0025 # Clear LCD display, payload: (identifier[2 bytes])
CMD_LCD_SET_CURSOR                  = 0x0026 # Set cursor position on LCD, payload: (identifier[2 bytes], row, column)    
CMD_LCD_WRITE_TEXT                  = 0x0027 # Write text to LCD, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_LCD_WRITE_TEXT_CENTER           = 0x0028 # Write centered text to LCD, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_LCD_WRITE_BITMAP                = 0x0029 # Write bitmap to LCD, payload: (identifier[2 bytes], Custom Characters by pixel data bytes)
CMD_LCD_SET_BACKGROUND              = 0x002A # Set LCD background color, payload: (identifier[2 bytes], R, G, B) only for RGB backlit LCDs
CMD_LCD_SET_CONTRAST                = 0x002B # Set LCD contrast, payload: (identifier[2 bytes], contrast level) 0-255 only for LCDs that support it
CMD_LCD_SAVE_SETTINGS               = 0x002F # Save LCD settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])
# OLED commands (0x003X)
CMD_OLED_CREATE                     = 0x0030 # Create OLED instance, payload: (identifier[2 bytes])
CMD_OLED_SETUP_I2C                  = 0x0031 # Setup OLED I2C, payload: (identifier[2 bytes], width[2 byte], height[2 byte], i2c identifier[2 bytes], i2c address[1 byte])
CMD_OLED_SETUP_SPI                  = 0x0032 # Setup OLED SPI, payload: (identifier[2 bytes], width[2 byte], height[2 byte], spi identifier[2 bytes], cs pin[1 byte], dc pin[1 byte], reset pin[1 byte])
CMD_OLED_CLEAR                      = 0x0035 # Clear OLED display, payload: (identifier[2 bytes])
CMD_OLED_SET_FONT                   = 0x0036 # Set OLED font, payload: (identifier[2 bytes], font identifier[1 byte])
CMD_OLED_WRITE_TEXT                 = 0x0037 # Write text to OLED, payload: (identifier[2 bytes], x_pos[2 bytes], y_pos[2 bytes], text bytes in UTF-8)
CMD_OLED_WRITE_TEXT_CENTER          = 0x0038 # Write centered text to OLED, payload: (identifier[2 bytes], text bytes in UTF-8)
CMD_OLED_CREATE_BUTTON              = 0x0039 # Create OLED button, payload: (identifier[2 bytes], x_pos[2 bytes], y_pos[2 bytes], width[2 bytes], height[2 bytes], corner radius[1 byte], color button[3 bytes], color label[3 bytes], label bytes in UTF-8)
CMD_OLED_WRITE_BITMAP               = 0x003A # Write bitmap to OLED, payload: (identifier[2 bytes], x_pos[2 bytes], y_pos[2 bytes], x_len[2 bytes], y_len[2 bytes], pixel data bytes)
CMD_OLED_SET_BRIGHTNESS             = 0x003B # Set OLED brightness, payload: (identifier[2 bytes], brightness level)
CMD_OLED_SET_CONTRAST               = 0x003C # Set OLED contrast, payload: (identifier[2 bytes], contrast level)
CMD_OLED_SAVE_SETTINGS              = 0x003F # Save OLED settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])
# Leave room for future display types (0x004X - 0x00EX)

# region Touchscreen CMDs
# Command definitions for Touchscreen operations (0x00FX)
CMD_TOUCHSCREEN_CREATE              = 0x00F0 # Create Touchscreen instance, payload: (identifier[2 bytes])
# Command definitions for Touchscreen I2C setup and configuration is not yet defined
CMD_TOUCHSCREEN_SETUP_SPI           = 0x00F2 # Setup Touchscreen SPI, payload: (identifier[2 bytes], spi identifier[2 bytes], cs pin[1 byte], dc pin[1 byte], reset pin[1 byte])
CMD_TOUCHSCREEN_READ_XY             = 0x00F5 # Read touchscreen X,Y coordinates, payload: (identifier[2 bytes]), returns: (x[2 bytes], y[2 bytes], pressed[1 byte])
CMD_TOUCHSCREEN_SAVE_SETTINGS       = 0x00FF # Save Touchscreen settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region Servo CMDs
# Command definitions for Servo operations (0x010X)
CMD_SERVO_ATTACH                    = 0x0100 # Attach servo to pin
CMD_SERVO_DETACH                    = 0x0101 # Detach servo from pin
CMD_SERVO_WRITE                     = 0x0102 # Write angle to servo

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
CMD_UART_SAVE_SETTINGS              = 0x020F # Save UART settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region I2C CMDs
# Command definitions for I2C operations (0x021X)
CMD_I2C_CREATE                      = 0x0210 # Create I2C instance, payload: (identifier[2 bytes])
CMD_I2C_SET_FREQUENCY               = 0x0211 # Set I2C frequency, payload: (identifier[2 bytes], frequency[4 bytes])
CMD_I2C_SET_PIN_CLOCK               = 0x0212 # Set I2C clock pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_SET_PIN_DATA                = 0x0213 # Set I2C data pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_READ                        = 0x0214 # I2C read, payload: (identifier[2 bytes], device address[1 byte], length), returns: (data bytes)
CMD_I2C_WRITE                       = 0x0215 # I2C write, payload: (identifier[2 bytes], device address[1 byte], data bytes...)
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
CMD_SPI_SAVE_SETTINGS               = 0x022F # Save SPI settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])
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
CMD_FIRMWARE_BUILD_FLAGS            = 0xFFFD # Response with build flags, returns: (build flags string in UTF-8)
CMD_FIRMWARE_INFO                   = 0xFFFE # Response with firmware info, returns (name string in UTF-8) # Name of the device configuration
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
        debug_enabled: bool = False,
        require_ack_on_send: bool = False,
        send_ack_timeout: float = 2.0,
        send_ready_timeout: float = 1.0,
        loop_delay: float = 0.0005,
    ):
        # Required parameters
        if transport_config is None:
            raise ValueError("transport_config must be provided and be a BaseTransportConfig instance")

        self.handshake_enabled = True
        self.handshake_timeout = 5.0
        self.transport_config = transport_config


        # [ ] TODO test auto_io behavior and sync() calls
        self.auto_io = self.transport_config.auto_io

        self.debug_enabled = debug_enabled








        self.debug_ok_received = 0


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
        self._ok_timestamps: List[datetime] = []

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



    # region Start/Stop
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

        # wait for device ready banner (handshake) before starting receiver
        if self.handshake_enabled:
            self.log_debug_message("Starting handshake to wait for device ready banner...")
            ok = self._await_device_ready(timeout=self.handshake_timeout)
            self.log_debug_message("handshake: ready=" + str(ok))
            # set readiness flag from handshake probe
            with self._ready_cv:
                self._ready = bool(ok)
                if self._ready:
                    self._ready_cv.notify_all()
            if not ok:
                self.stop()
                raise RuntimeError("handshake failed: device not ready within timeout")
        else:
            time.sleep(0.25)  # brief pause to allow transport to settle
            self.log_debug_message("Handshake disabled; assuming device is ready")
            # set readiness flag
            with self._ready_cv:
                self._ready = True
                self._ready_cv.notify_all()

        # start receive thread
        self._recv_thread = threading.Thread(target=self._recv_worker, daemon=True)
        self._recv_thread.start()
        self.log_debug_message("#### GPIO_Lib started successfully ####")
        return True     # started successfully
    
    def stop(self) -> None:
        """Stop GPIO_Lib operation and worker threads."""
        if not self._running:
            self.log_debug_message("stop() called but GPIO_Lib not running")
            return

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
        self.log_debug_message(f"Building packet: CMD=0x{int(cmd):04X}, LEN={length}, PAYLOAD={payload.hex()}, CHK=0x{chk:02X}")
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

    # region queueing
    def _add_packet_to_send_queue(self, packet: bytes, wait_ack: bool = False) -> bool:
        """Enqueue a framed packet for delivery by the send worker.

        Returns True when enqueued (convenience for callers/tests).
        """
        # Sanity check packet for external callers
        if self._validatePacket(packet) is False:
            raise ValueError("enqueue_packet: invalid packet checksum")
        
        self.log_debug_message(f"enqueue packet len={len(packet)} wait_ack={wait_ack} hex={packet.hex()}")
        self._send_q.put((packet, bool(wait_ack)))
        return True
    
    def await_send_empty(self, timeout: float | None = None) -> bool:
        """Block until the send queue is empty and any in-progress send completes.

        Returns True if the buffer emptied, False if timed out.
        """
        end = time.time() + float(timeout) if timeout is not None else None
        while True:
            if self._send_q.empty() and not self._send_in_progress:
                return True
            if end is not None and time.time() > end:
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
            # small pause to yield to other threads
            time.sleep(self.loop_delay)

            try:
                packet, wait_ack = self._send_q.get(timeout=0.2)
            except Exception:
                # no packet, continue
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
                    self._transport.send(packet)
                except Exception as e:
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
            # small pause to yield to other threads
            time.sleep(self.loop_delay)

            data = self._transport.receive_bytes()
            if not data:
                continue
            self.log_debug_message(f"Received data: {data!r}")

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















































































    # [ ] TODO subclasses for peripherals. API call: GPIO_Lib.gpio.pin_mode() etc.


    # --- configuration (Arduino-like API) ------------------------

    def _encode_pin(self, p: int) -> bytes:
        if p < 0 or p > 0xFFFF:
            raise ValueError("pin out of range")
        if p <= 0xFF:
            return bytes([p & 0xFF])
        return bytes([p & 0xFF, (p >> 8) & 0xFF])

    def pin_mode(self, pin: int | str, mode: str, name: Optional[str] = None) -> None:
        """Configure `pin` with `mode` and optional `name`.

        mode: one of 'INPUT', 'OUTPUT', 'INPUT_PULLUP', 'INPUT_PULLDOWN',
              'ANALOG_INPUT', 'ANALOG_OUTPUT'

        If `pin` is a string name, a numeric pin must be provided via `name`
        mapping elsewhere; prefer numeric pin values.
        """
        if isinstance(pin, str) and not pin.isnumeric():
            raise ValueError("pin_mode requires a numeric pin; use names only for read/write ops")
        pin_num = int(pin)
        if name:
            self.pin_to_name[pin_num] = name

        # update mirrors
        m = mode.upper()
        if m == "OUTPUT":
            self.outputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_OUTPUT
            payload = self._encode_pin(pin_num)
        elif m == "INPUT":
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT
            payload = self._encode_pin(pin_num)
        elif m == "INPUT_PULLUP":
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT_PULLUP
            payload = self._encode_pin(pin_num)
        elif m == "INPUT_PULLDOWN":
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "digital"})
            cmd = CMD_DIGITAL_INPUT_PULLDOWN
            payload = self._encode_pin(pin_num)
        elif m == "ANALOG_INPUT":
            self.inputs.setdefault(name or str(pin_num), {"pin": pin_num, "value": 0, "type": "analog"})
            cmd = CMD_ANALOG_INPUT
            payload = self._encode_pin(pin_num)
        elif m == "ANALOG_OUTPUT":
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

    # Arduino-style alias
    pinMode = pin_mode

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
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.inputs.get(name)
            if entry is None:
                raise ValueError(f"input name not found: {name}")
            return bool(entry["value"])
        else:
            pin_num = int(pin)
            name = self.pin_to_name.get(pin_num)
            if name and name in self.inputs:
                return bool(self.inputs[name]["value"])
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
            # encode pin and value
            if pin_num <= 0xFF:
                payload = bytes([pin_num & 0xFF, int(val) & 0xFF])
            else:
                payload = bytes([pin_num & 0xFF, (pin_num >> 8) & 0xFF, int(val) & 0xFF])
            packet = self._build_packet(cmd, payload)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    def analog_read(self, pin: int | str) -> int:
        if isinstance(pin, str) and not pin.isnumeric():
            name = pin
            entry = self.inputs.get(name)
            if entry is None:
                raise ValueError(f"input name not found: {name}")
            return int(entry["value"])
        else:
            pin_num = int(pin)
            name = self.pin_to_name.get(pin_num)
            if name and name in self.inputs:
                return int(self.inputs[name]["value"])
            return 0

    def servo_write(self, index: int, val: int) -> None:
        self.servo_array[index] = int(val)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_SERVO_WRITE
            payload = bytes([index & 0xFF, int(val) & 0xFF])
            packet = self._build_packet(cmd, payload)
            self._add_packet_to_send_queue(packet, wait_ack=False)

    def lcd_write(self, text: str) -> None:
        # simple append model; device is expected to handle display payloads
        self.lcd_lines.append(text)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_LCD_WRITE_TEXT
            b = text.encode(errors="replace")
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
            else:
                cmd = CMD_DIGITAL_WRITE
            # encode pin index as 1 or 2 bytes then append value
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
    

    def _handle_packet(self, cmd: int, payload: bytes) -> None:
        # handle incoming command frames (device -> host updates)
        # Device-level status
        if cmd == CMD_DEVICE_OK:
            # timestamped debug + notify waiters; also record a precise timestamp for plotting
            ts = datetime.now().isoformat(timespec='milliseconds')
            try:
                if self.debug_enabled:
                    self.log_debug_message(f"device: OK")
            except Exception:
                if self.debug_enabled:
                    print(f"device: OK")
            # increment counter, record timestamp, and wake waiters
            with self._ok_cv:
                self.debug_ok_received += 1
                try:
                    self._ok_timestamps.append(datetime.fromisoformat(ts))
                except Exception:
                    # fallback: append naive datetime.now()
                    self._ok_timestamps.append(datetime.now())
                self._ok_cv.notify_all()
            return
        if cmd == CMD_DEVICE_ERROR:
            if self.debug_enabled:
                print("device: ERROR", payload)
            return

        # Digital read responses
        if cmd == CMD_DIGITAL_READ and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            # update input mirror by pin -> name mapping
            name = self.pin_to_name.get(pin)
            if name:
                if name not in self.inputs:
                    self.inputs[name] = {"pin": pin, "value": int(val), "type": "digital"}
                else:
                    self.inputs[name]["value"] = int(val)
            else:
                # unknown pin, create a numeric-keyed entry
                self.inputs[str(pin)] = {"pin": pin, "value": int(val), "type": "digital"}
            if self.debug_enabled:
                print(f"input update pin={pin} val={val}")
            return

        # Output updates (device echo)
        if cmd == CMD_DIGITAL_WRITE and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            name = self.pin_to_name.get(pin)
            if name:
                if name not in self.outputs:
                    self.outputs[name] = {"pin": pin, "value": int(val), "type": "digital"}
                else:
                    self.outputs[name]["value"] = int(val)
            else:
                self.outputs[str(pin)] = {"pin": pin, "value": int(val), "type": "digital"}
            return

        # Analog read responses
        if cmd == CMD_ANALOG_READ and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            name = self.pin_to_name.get(pin)
            if name:
                if name not in self.inputs:
                    self.inputs[name] = {"pin": pin, "value": int(val), "type": "analog"}
                else:
                    self.inputs[name]["value"] = int(val)
            else:
                self.inputs[str(pin)] = {"pin": pin, "value": int(val), "type": "analog"}
            if self.debug_enabled:
                print(f"analog input update pin={pin} val={val}")
            return

        # Analog write echo/update
        if cmd == CMD_ANALOG_WRITE and len(payload) >= 2:
            pin, val = payload[0], payload[1]
            name = self.pin_to_name.get(pin)
            if name:
                if name not in self.outputs:
                    self.outputs[name] = {"pin": pin, "value": int(val), "type": "analog"}
                else:
                    self.outputs[name]["value"] = int(val)
            else:
                self.outputs[str(pin)] = {"pin": pin, "value": int(val), "type": "analog"}
            return

        # Servo updates
        if cmd == CMD_SERVO_WRITE and len(payload) >= 2:
            idx_servo, val = payload[0], payload[1]
            self.servo_array[idx_servo] = int(val)
            return

        # LCD text
        if cmd == CMD_LCD_WRITE_TEXT and len(payload) >= 1:
            try:
                text = payload.decode(errors="replace")
            except Exception:
                text = ""
            self.lcd_lines.append(text)
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
