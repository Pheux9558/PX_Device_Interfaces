from __future__ import annotations

from enum import IntEnum
import os
import struct
import struct
import threading
import time
import queue
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional

from px_device_interfaces.transports import BaseTransport, MockTransport
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


# region Uno R4 Matrix CMDs
# Arduino Uno R4 Onboard red dot led matrix
CMD_UNO_R4_MATRIX_CREATE            = 0x0060 # Create Uno R4 Matrix instance, (Only one Instance supported)
CMD_UNO_R4_MATRIX_CLEAR             = 0x0061 # Clear the matrix, payload: none
CMD_UNO_R4_MATRIX_SET_PIXEL         = 0x0062 # Set pixel color, payload: (x[1 byte], y[1 byte], v[1 byte]) # led has one color with start on or off
CMD_UNO_R4_MATRIX_WRITE_TEXT        = 0x0063 # Write text, payload: (speed[1 byte], text bytes in UTF-8) # speed is optional (0 = no scroll) and can be used for text scrolling
CMD_UNO_R4_MATRIX_ANIMATION         = 0x0064 # Start animation, payload: (strat/stop [1 byte], speed[1 byte], (id [1 byte]) optional) ) # speed is used to control the speed of the animation, and id can be used to show animations from Arduino lib. The frame data for the animation can be sent with the CMD_UNO_R4_MATRIX_SET_ANIMATION_FRAME command.
CMD_UNO_R4_MATRIX_SET_ANIMATION_FRAME         = 0x0065 # Set frame for animation, payload: (frame number[1 byte], led data bytes...) # led data is streamed as x,y,v tuples until the end of the payload. Frame number can be used to manage multiple frames for animations.
CMD_UNO_R4_MATRIX_SET_CUSTOM_FRAME  = 0x0066 # Set custom frame (0-15), payload: (frame_id[1 byte], led data as x,y,v tuples...)
CMD_UNO_R4_MATRIX_SHOW_CUSTOM_FRAME = 0x0067 # Show custom frame (0-15), payload: (frame_id[1 byte])
CMD_UNO_R4_MATRIX_SET_CUSTOM_ANIMATION = 0x0068 # Set custom animation (0-3, max 8 frames each), payload: (animation_id[1 byte], num_frames[1 byte], loop[1 byte], frame_data[...]) # frame_data is num_frames * 12-byte bitmaps
CMD_UNO_R4_MATRIX_SHOW_CUSTOM_ANIMATION = 0x0069 # Show custom animation (0-3), payload: (animation_id[1 byte], speed[1 byte])
CMD_UNO_R4_MATRIX_WRITE_BITMAP_DIRECT = 0x006A # Write bitmap directly to display (no storage), payload: (led data as x,y,v tuples...)

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

# region Ethernet CMDs
# Command definitions for Ethernet operations (0x029X)
# [ ] Ethernet commands can be defined here

# region Encoder CMDs
# Command definitions for Encoder operations (0x031X)
CMD_ENCODER_CREATE                  = 0x0310 # Create Encoder instance, payload: (identifier[2 bytes])
CMD_ENCODER_SET_PINS                = 0x0311 # Set Encoder pins, payload: (identifier[2 bytes], pin A[1 byte], pin B[1 byte], optionally pin Z[1 byte])
CMD_ENCODER_SET_PPR                 = 0x0312 # Set Encoder pulses per revolution, payload: (identifier[2 bytes], ppr[2 bytes])
CMD_ENCODER_READ                    = 0x0313 # Read Encoder, payload: (identifier[2 bytes]), returns: (position[4 bytes], direction[1 byte], optionally Z state[1 byte], optionally revolutions[4 bytes])
CMD_ENCODER_RESET                   = 0x0314 # Reset encoder counters to zero, payload: (identifier[2 bytes])
CMD_ENCODER_FLIP                    = 0x0315 # Toggle encoder direction inversion, payload: (identifier[2 bytes])
# [ ] TODO Save Encoder settings command to save Encoder configuration to non-volatile memory for automatic setup on startup
# CMD_ENCODER_SAVE_SETTINGS           = 0x031F # Save Encoder settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# region Stepper Motor CMDs
# Command definitions for unit-aware Stepper Motor operations (0x032X)
CMD_STEPPER_CREATE            = 0x0320 # Create Stepper instance, payload: id[2]
CMD_STEPPER_SET_PINS          = 0x0321 # Configure pins: id[2] step[1] dir[1] driver_type[1] enable[1] fault[1] sleep[1] m0[1] m1[1] m2[1]
CMD_STEPPER_SET_ENCODER       = 0x0322 # Attach encoder: id[2] enc_id[2] enc_ppr[2]
CMD_STEPPER_SET_PID           = 0x0323 # PID gains: id[2] kp[4f] ki[4f] kd[4f]
CMD_STEPPER_SET_MICROSTEP     = 0x0324 # Set microstep divisor/mode: id[2] divisor[1]
CMD_STEPPER_CONFIGURE_MOTION  = 0x0325 # Configure user-unit motion: id[2] unit_mode[1] steps_per_rev[2] steps_per_mm_full[4f] max_speed[4f] max_accel[4f]
CMD_STEPPER_MOVE_TO_UNITS     = 0x0326 # Move to user-unit target: id[2] unit_mode[1] target[4f] speed_override[4f] accel_override[4f]
CMD_STEPPER_GET_STATUS        = 0x0327 # Read unit-aware status: id[2] -> id[2] state[1] unit_mode[1] pos_user[4f] speed_user[4f] moving[1] fault[1] fault_flags[1] pos_steps[4] speed_sps[4f]
CMD_STEPPER_STOP              = 0x0328 # Stop: id[2] immediate[1]
CMD_STEPPER_ENABLE            = 0x0329 # Enable/disable driver: id[2] enable[1]
CMD_STEPPER_CONFIGURE_HOMING  = 0x032A # Configure homing: id[2] speed[4f] accel[4f] end_stop_left[1] end_stop_right[1] flags[1]
CMD_STEPPER_HOME              = 0x032B # Start homing using configured homing settings: id[2]
CMD_STEPPER_SET_DIRECTION     = 0x032C # Set direction inversion: id[2] invert[1]
CMD_STEPPER_SET_POSITION_UNITS = 0x032D # Set current absolute position in current unit mode: id[2] unit_mode[1] position[4f]
CMD_STEPPER_CLEAR_FAULT       = 0x032E # Clear fault state: id[2]
CMD_STEPPER_INIT              = 0x032F # Run driver startup sequence: id[2]



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




# region Return codes
# General response codes
CMD_DEVICE_OK                       = 0x1000 # General OK response (e.g. Response to valid commands or acknowledgements for actions)
CMD_DEVICE_ERROR                    = 0x1001 # General ERROR response (e.g. Response to invalid commands or parameters)

# Controll codes
CMD_SYS_GET_STATS                   = 0xFFFA
CMD_FIRMWARE_RESET                  = 0xFFFC # Reset the device, no payload. Response with CMD_BANNER_GPIO_READY after reboot and initialization. Note: this command will cause the device to disconnect and reconnect if using USB CDC, so the transport may need to be re-established on the host side after sending this command.
CMD_FIRMWARE_BUILD_FLAGS            = 0xFFFD # Response with build flags, returns: (build flags string in UTF-8)
CMD_FIRMWARE_NAME                   = 0xFFFE # Response with firmware name, returns (name string in UTF-8) # Name of the device configuration
CMD_FIRMWARE_VERSION                = 0xFFFF # Response with firmware version, returns: (major, minor, patch)

# Controll Banners
CMD_BANNER_GPIO_READY               = "GPIO_READY" # GPIO_READY banner indicating device is ready for operation
# endregion Return codes from device

# Reverse lookup: CMD value -> name string (built once at module load)
_CMD_NAMES: dict[int, str] = {
    v: k for k, v in globals().items()
    if k.startswith("CMD_") and isinstance(v, int)
}


def _cmd_name(cmd: int) -> str:
    """Return 'CMD_NAME (0xXXXX)' for a known command, or '0xXXXX' if unknown."""
    name = _CMD_NAMES.get(cmd)
    return f"{name} (0x{cmd:04X})" if name else f"0x{cmd:04X}"


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
        send_ack_timeout: float = 2.0,
        send_ready_timeout: float = 1.0,
        loop_delay: float = 0.0005,
        debug_enabled: bool | None = None,
        raise_on_CMD_DEVICE_ERROR: bool = True,
    ):
        # Required parameters
        if transport_config is None:
            raise ValueError("transport_config must be provided and be a BaseTransportConfig instance")

        self.handshake_enabled = True
        self.handshake_raise_on_timeout = True
        self.handshake_timeout = 5.0
        self.transport_config = transport_config

        self.reset_on_start = True
        self.raise_on_CMD_DEVICE_ERROR = raise_on_CMD_DEVICE_ERROR


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
        self._pending_exception_lock = threading.Lock()
        self._pending_exception: Optional[Exception] = None
        self._device_error_latched = False

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
    
    # region Loop delay config
    def setLoopDelay(self, delay: float) -> None:
        """Adjust the small delay between consecutive sends (seconds)."""
        self.loop_delay = float(delay)
    
    def getLoopDelay(self) -> float:
        """Return the current loop delay between sends (seconds)."""
        return self.loop_delay

    def _set_pending_exception(self, exc: Exception) -> None:
        with self._pending_exception_lock:
            if self._pending_exception is None:
                self._pending_exception = exc
                self._device_error_latched = True

        with self._ok_cv:
            self._ok_cv.notify_all()
        with self._ready_cv:
            self._ready_cv.notify_all()
        with self._resp_cv:
            self._resp_cv.notify_all()

    def _peek_pending_exception(self) -> Optional[Exception]:
        with self._pending_exception_lock:
            return self._pending_exception

    def _raise_pending_exception(self) -> None:
        with self._pending_exception_lock:
            exc = self._pending_exception
            self._pending_exception = None
        if exc is not None:
            raise exc

    def _clear_pending_exception(self) -> None:
        with self._pending_exception_lock:
            self._pending_exception = None
            self._device_error_latched = False

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
        print(f"GPIO_Lib: requestFirmwareInfo timed out after {timeout}s")
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
        """Start GPIO_Lib operation and worker threads.

        Returns True on success, False if startup/connection fails.
        """
        if self._running:
            return False # already running

        self._clear_pending_exception()
        
        # Create transport from the provided dataclass config (no kwargs path)
        if not hasattr(self.transport_config, "create_transport"):
            raise ValueError("transport_config must implement create_transport() and produce a BaseTransport instance")
        self._transport = self.transport_config.create_transport()
        if not self._transport:
            raise RuntimeError("no transport available from transport_config.create_transport()")

        # Link debug print functions
        self._transport.set_debug_function(self.log_debug_message)

        # if mocking. set timeouts realy low
        if isinstance(self._transport, MockTransport):
            self.log_debug_message("Using MockTransport, setting timeouts to very low values for testing")
            self.handshake_timeout = 0.5
            self.send_ack_timeout = 0.5
            self.send_ready_timeout = 0.5

        # attempt connect and ensure the transport reports connected state
        try:
            connected = self._transport.connect()
        except Exception as e:
            self.log_debug_message(f"transport connect() raised exception: {e}")
            return False

        if not connected:
            self.log_debug_message("transport failed to connect")
            return False
        if not self._transport.is_connected:
            self.log_debug_message("transport is not connected after connect()")
            try:
                self._transport.disconnect()
            except Exception:
                pass
            return False

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
            if not self.resetDevice():
                self.log_debug_message("start(): reset/handshake failed")
                self._running = False
                if self._transport and self._transport.is_connected:
                    self._transport.disconnect()
                return False


        # Check thread status and log
        if not self._send_thread.is_alive():
            self.log_debug_message("send thread failed to start")
            self._running = False
            if self._transport and self._transport.is_connected:
                self._transport.disconnect()
            return False
        if not self._recv_thread or not self._recv_thread.is_alive():
            self.log_debug_message("recv thread failed to start")
            self._running = False
            if self._transport and self._transport.is_connected:
                self._transport.disconnect()
            return False
        
        # Wait till config is transmitted to device
        if not self.await_send_empty():
            self.log_debug_message("start(): send queue failed to drain")
            self._running = False
            if self._transport and self._transport.is_connected:
                self._transport.disconnect()
            return False

        self.log_debug_message("#### GPIO_Lib started successfully ####")
        return True     # started successfully
    
    # region Stop GPIO_Lib
    def stop(self, timeout: float = 5.0) -> None:
        """Stop GPIO_Lib operation and worker threads."""
        if not self._running:
            self.log_debug_message("stop() called but GPIO_Lib not running")
            return

        try:
            self.await_send_empty(timeout=timeout)
        except Exception as e:
            self.log_debug_message(f"stop(): ignoring pending exception during shutdown: {e}")
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

        self._clear_pending_exception()

        self.log_debug_message("GPIO_Lib stopped")
        print("") # newline for readability after stop
        # Print summary of debug info
        print(f"Total sent: {self.total_sent_bytes} bytes, Total received: {self.total_received_bytes} bytes")
        print(f"Total OK frames received: {self.debug_ok_received}")

    @property
    def connected(self) -> bool:
        """Return True if transport is connected, False otherwise."""
        return self._transport.is_connected if self._transport else False
    
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

    def _probe_device_ready_via_protocol(self, timeout: float = 5.0) -> bool:
        """Actively probe the device after reconnect using the binary protocol.

        Some targets may not expose the textual GPIO_READY banner reliably after
        a USB CDC reconnect. In that case, a valid firmware-version response is
        sufficient proof that the protocol stack is alive.
        """
        if not self._transport or not self._transport.is_connected:
            self.log_debug_message("probe_device_ready: transport not connected")
            return False

        try:
            self._transport.send(self._build_packet(CMD_FIRMWARE_VERSION, b""))
        except Exception as e:
            self.log_debug_message(f"probe_device_ready: failed to send probe: {e}")
            return False

        end = time.time() + max(float(timeout), 0.5)
        buf = bytearray()
        self.log_debug_message("Probing device readiness via CMD_FIRMWARE_VERSION...")

        while time.time() < end:
            time.sleep(0.05)
            try:
                received_data = self._transport.receive_bytes()
            except Exception as e:
                self.log_debug_message(f"probe_device_ready: receive failed: {e}")
                return False

            if not received_data:
                continue

            decoded_received_data = received_data.decode(errors="ignore")
            if CMD_BANNER_GPIO_READY in decoded_received_data:
                self.log_debug_message("probe_device_ready: observed GPIO_READY banner")
                with self._ready_cv:
                    self._ready = True
                    self._ready_cv.notify_all()
                return True

            buf.extend(received_data)
            while True:
                res = self._parse_frame(buf)
                if not res:
                    break
                cmd, payload = res
                if cmd == CMD_FIRMWARE_VERSION and len(payload) == 3:
                    self.log_debug_message(
                        f"probe_device_ready: firmware version {payload[0]}.{payload[1]}.{payload[2]}"
                    )
                    with self._ready_cv:
                        self._ready = True
                        self._ready_cv.notify_all()
                    return True

        self.log_debug_message("probe_device_ready: timed out waiting for firmware response")
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
        self._raise_pending_exception()

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
            self._raise_pending_exception()
            self.log_debug_message("Send queue already empty and no send in progress")
            return True
        
        self.log_debug_message("Awaiting send queue to empty...")
        end = time.time() + float(timeout) if timeout is not None else None
        while True:
            self._raise_pending_exception()
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
                raise TimeoutError(f"await_send_empty: send queue did not empty within {timeout}s")
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
            if self._device_error_latched:
                time.sleep(self.loop_delay)
                continue

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
                send_failed = False
                try:
                    self.total_sent_bytes += len(packet)
                    self.last_send_data = packet
                    self._transport.send(packet)
                except Exception as e:
                    send_failed = True
                    exc = ConnectionError(f"transport send failed: {e}")
                    print(f"GPIO_Lib send_worker: {exc}")
                    self._set_pending_exception(exc)

                # optionally wait for device OK (skip if send already failed)
                if wait_ack and not send_failed:
                    start = self.debug_ok_received
                    with self._ok_cv:
                        waited = self._ok_cv.wait_for(lambda: self.debug_ok_received > start, timeout=self.send_ack_timeout)
                    if not waited:
                        exc = TimeoutError(
                            f"device did not ACK within {self.send_ack_timeout}s "
                            f"(packet: {packet.hex()})"
                        )
                        print(f"GPIO_Lib send_worker: {exc}")
                        self._set_pending_exception(exc)

            finally:
                self._send_q.task_done()
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

            try:
                data = self._transport.receive_bytes()
            except Exception as e:
                exc = ConnectionError(f"transport receive failed: {e}")
                print(f"GPIO_Lib recv_worker: {exc}")
                self._set_pending_exception(exc)
                break
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
    def resetDevice(self) -> bool:
        """Send a reset command to the device via the firmware protocol. 
        This will cause the device to reboot, so the transport may disconnect and reconnect (e.g. USB CDC). 
        After sending the reset command, this method waits for the device to become ready again.
        Returns True on successful post-reset recovery, False on timeout/failure.
        """
        if not self._transport:
            raise RuntimeError("resetDevice: transport not initialized")
        
        try:
            with self._ready_cv:
                self._ready = False

            self._add_packet_to_send_queue(self._build_packet(CMD_FIRMWARE_RESET, b""), wait_ack=False)
            # wait for device ok response to ensure the reset command was processed before proceeding with thread shutdown and handshake
            with self._ok_cv:
                start_ok_count = self.debug_ok_received
                waited = self._ok_cv.wait_for(lambda: self.debug_ok_received > start_ok_count, timeout=self.handshake_timeout)
            if not waited and self.debug_enabled:
                self.log_debug_message("resetDevice: timed out waiting for device OK after sending firmware reset command")
            self.log_debug_message("Device reset command sent via firmware protocol")

            return self._handshake_after_boot_reset()
        except Exception as e:
            self.log_debug_message(f"Error sending firmware reset command: {e}")
            return False

    # region Reconnect transport after reset
    def _reconnect_transport_after_reset(self, timeout: float) -> bool:
        """Reconnect the underlying transport after a device reboot.

        USB CDC devices can disappear and re-enumerate during reset, so the old
        serial handle cannot be trusted after CMD_FIRMWARE_RESET.
        """
        if not self._transport:
            return False

        try:
            self._transport.disconnect()
        except Exception:
            pass

        end = time.time() + max(float(timeout), 0.5)
        while time.time() < end:
            try:
                if self._transport.connect() and self._transport.is_connected:
                    self.log_debug_message("Transport reconnected after reset")
                    return True
            except Exception as e:
                self.log_debug_message(f"Reconnect attempt failed: {e}")
            time.sleep(0.1)

        self.log_debug_message("Timed out reconnecting transport after reset")
        return False

    # region Handshake after boot reset
    def _handshake_after_boot_reset(self) -> bool:
        if not self.handshake_enabled:
            self.log_debug_message("Handshake disabled; skipping post-reset handshake")
            time.sleep(0.25)
            return self._reconnect_transport_after_reset(self.handshake_timeout)

        # Stop receive thread to avoid processing incoming data during reset
        if self._recv_thread and self._recv_thread.is_alive():
            self.log_debug_message("Waiting for receive thread to stop before proceeding with reset...")
            self.stopReceiveWorkerRequested = True
            self._recv_thread.join(2.0)  # Increased timeout from 0.5 to 2.0 seconds
            if self._recv_thread.is_alive():
                self.log_debug_message("ERROR: Receive thread did not stop in time; cannot proceed safely")
                return False
            else:
                self.log_debug_message("Receive thread stopped successfully")
        
        ok = False
        try:
            if not self._reconnect_transport_after_reset(self.handshake_timeout):
                return False

            # If handshake is enabled, wait for the device to become ready again after reset
            if self.handshake_enabled:
                self.log_debug_message("Waiting for device to become ready after reset...")
                try:
                    ok = self._await_device_ready(timeout=self.handshake_timeout)
                except TimeoutError:
                    ok = False
                if not ok:
                    self.log_debug_message("Ready banner not observed; falling back to active probe")
                    ok = self._probe_device_ready_via_protocol(timeout=self.handshake_timeout)
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
                ok = True
        finally:
            # Always attempt to restart the receive thread if we stopped it above.
            if self.stopReceiveWorkerRequested and ok and self._running and self._transport and self._transport.is_connected:
                self.stopReceiveWorkerRequested = False
                self._recv_thread = threading.Thread(target=self._recv_worker, daemon=True)
                self._recv_thread.start()
                self.log_debug_message("Receive thread started after reset")
            else:
                self.stopReceiveWorkerRequested = False

        return ok



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

    class Encoder:
        """Quadrature encoder peripheral handler."""
        total_instances = 0

        def __init__(
            self,
            gpio_lib: GPIO_Lib,
            pin_a: int,
            pin_b: int,
            pin_z: Optional[int] = None,
            ppr: int = 1024,
        ) -> None:
            self.gpio_lib = gpio_lib
            self.identifier = gpio_lib.Encoder.total_instances
            gpio_lib.Encoder.total_instances += 1

            self.pin_a = int(pin_a)
            self.pin_b = int(pin_b)
            self.pin_z = int(pin_z) if pin_z is not None else None
            self.ppr = int(ppr)
            self._setup_complete = False

        def setup(self) -> None:
            if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                raise RuntimeError("Encoder: GPIO_Lib transport not connected")
            if self.pin_a < 0 or self.pin_a > 0xFF:
                raise ValueError("Encoder: pin_a out of range (0-255)")
            if self.pin_b < 0 or self.pin_b > 0xFF:
                raise ValueError("Encoder: pin_b out of range (0-255)")
            if self.pin_z is not None and (self.pin_z < 0 or self.pin_z > 0xFF):
                raise ValueError("Encoder: pin_z out of range (0-255)")
            if self.ppr <= 0 or self.ppr > 0xFFFF:
                raise ValueError("Encoder: ppr out of range")

            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_ENCODER_CREATE, payload), wait_ack=False
            )

            payload = self.identifier.to_bytes(2, "little") + bytes([self.pin_a & 0xFF, self.pin_b & 0xFF])
            if self.pin_z is not None:
                payload += bytes([self.pin_z & 0xFF])
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_ENCODER_SET_PINS, payload), wait_ack=False
            )

            payload = self.identifier.to_bytes(2, "little") + int(self.ppr).to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_ENCODER_SET_PPR, payload), wait_ack=False
            )

            self._setup_complete = True

        def read(self, timeout: float = 1.0) -> Dict[str, int | bool]:
            if not self._setup_complete:
                self.setup()
            payload = self.identifier.to_bytes(2, "little")
            packet = self.gpio_lib._build_packet(CMD_ENCODER_READ, payload)
            self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
            resp = self.gpio_lib._await_response(CMD_ENCODER_READ, self.identifier, timeout=timeout)
            if len(resp) < 5:
                raise RuntimeError("Encoder: invalid read response payload")

            position = int.from_bytes(resp[0:4], "little", signed=True)
            direction = int.from_bytes(resp[4:5], "little", signed=True)
            z_state = bool(resp[5]) if len(resp) >= 6 else False
            revolutions = int.from_bytes(resp[6:10], "little", signed=True) if len(resp) >= 10 else 0
            return {
                "position": position,
                "revolutions": revolutions,
                "direction": direction,
                "z": z_state,
            }

        def reset(self) -> None:
            if not self._setup_complete:
                self.setup()
            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_ENCODER_RESET, payload), wait_ack=False
            )

        def flip(self) -> None:
            """Toggle encoder direction so counts increase when the motor moves forward."""
            if not self._setup_complete:
                self.setup()
            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_ENCODER_FLIP, payload), wait_ack=False
            )


    class Stepper:
        """Stepper motor base class.

        Supports generic step/dir drivers.  Driver-specific subclasses
        (StepperSTSPIN220, StepperDRV8825) extend the pin set and set
        the correct ``driver_type`` automatically.

        Quick start::

            stepper = gpio_lib.Stepper(gpio_lib, step_pin=2, dir_pin=3, enable_pin=4)
            stepper.setup()
            stepper.set_speed(400)         # steps/sec
            stepper.set_acceleration(400)  # steps/sec²
            stepper.move(1000)             # move 1000 steps forward
        """

        # Driver type constants (must match firmware enum)
        DRIVER_GENERIC   = 0
        DRIVER_STSPIN220 = 1
        DRIVER_DRV8825   = 2

        # Sentinel: pin not wired
        _PIN_NONE = 0xFF
        _UNIT_NONE = 0
        _UNIT_MM = 1
        _UNIT_REV = 2
        _STATUS_IDLE = 0
        _STATUS_ACCELERATING = 1
        _STATUS_MOVING = 2
        _STATUS_DECELERATING = 3
        _STATUS_HOMING = 4
        _STATUS_FAULT = 5

        # Public aliases for status codes (stable external API)
        STATUS_IDLE = _STATUS_IDLE
        STATUS_ACCELERATING = _STATUS_ACCELERATING
        STATUS_MOVING = _STATUS_MOVING
        STATUS_DECELERATING = _STATUS_DECELERATING
        STATUS_HOMING = _STATUS_HOMING
        STATUS_FAULT = _STATUS_FAULT

        class MICROSTEPS(IntEnum):
            FULL = 1
            X1_2 = 2
            X1_4 = 4
            X1_8 = 8
            X1_16 = 16
            X1_32 = 32
            X1_64 = 64
            X1_128 = 128
            X1_256 = 256

        _MICROSTEP_MODE_TO_DIV = {
            "full": 1,
            "half": 2,
            "quarter": 4,
            "eighth": 8,
            "sixteenth": 16,
            "thirty-second": 32,
            "sixty-fourth": 64,
            "one-twenty-eighth": 128,
            "two-fifty-sixth": 256,
        }
        _DIV_TO_MICROSTEP_MODE = {value: key for key, value in _MICROSTEP_MODE_TO_DIV.items()}
        _UNIT_CODE_TO_NAME = {
            _UNIT_NONE: "none",
            _UNIT_MM: "mm",
            _UNIT_REV: "rev",
        }
        _UNIT_NAME_TO_CODE = {value: key for key, value in _UNIT_CODE_TO_NAME.items()}
        _STATUS_CODE_TO_NAME = {
            _STATUS_IDLE: "idle",
            _STATUS_ACCELERATING: "accelerating",
            _STATUS_MOVING: "moving",
            _STATUS_DECELERATING: "decelerating",
            _STATUS_HOMING: "homing",
            _STATUS_FAULT: "fault",
        }

        # Driver-specific constructors are attached later in the class body,
        # but we declare them here so static analyzers can see the API.
        StepperSTSPIN220: ClassVar[type["GPIO_Lib._StepperSTSPIN220Impl"]]
        StepperDRV8825: ClassVar[type["GPIO_Lib._StepperDRV8825Impl"]]
        total_instances = 0

        def __init__(
            self,
            gpio_lib: "GPIO_Lib",
            step_pin: int,
            dir_pin: int,
            enable_pin: Optional[int] = None,
            fault_pin: Optional[int] = None,
            m0_pin: Optional[int] = None,
            m1_pin: Optional[int] = None,
            m2_pin: Optional[int] = None,
            steps_per_revolution: int = 200,
            max_speed: int = 400,
            acceleration: int = 400,
            *,
            _driver_type: int = 0,
        ) -> None:
            self.gpio_lib = gpio_lib
            self.identifier = GPIO_Lib.Stepper.total_instances
            GPIO_Lib.Stepper.total_instances += 1

            self.step_pin   = int(step_pin)
            self.dir_pin    = int(dir_pin)
            self.enable_pin = int(enable_pin) if enable_pin is not None else None
            self.fault_pin  = int(fault_pin)  if fault_pin  is not None else None
            self.m0_pin     = int(m0_pin)     if m0_pin     is not None else None
            self.m1_pin     = int(m1_pin)     if m1_pin     is not None else None
            self.m2_pin     = int(m2_pin)     if m2_pin     is not None else None
            self._sleep_pin: Optional[int] = None   # overridden by STSPIN220

            self.steps_per_revolution = int(steps_per_revolution)
            self.max_speed            = int(max_speed)
            self.acceleration         = int(acceleration)
            self.microstep_div        = 1
            self.steps_per_mm: Optional[float] = None
            self.full_steps_per_mm: Optional[float] = None
            self.unit_mode = "none"
            self.max_speed_user: Optional[float] = None
            self.max_acceleration_user: Optional[float] = None
            self.homing_speed_user: Optional[float] = None
            self.homing_acceleration_user: Optional[float] = None
            self.homing_end_stop_left: Optional[int] = None
            self.homing_end_stop_right: Optional[int] = None
            self.direction_inverted = False

            self._driver_type   = int(_driver_type)
            self._setup_complete = False
            self._has_encoder    = False
            self._encoder_ref: Optional["GPIO_Lib.Encoder"] = None

        # ── Accessors ──────────────────────────────────────────────

        def set_speed(self, steps_per_sec: int) -> None:
            self.max_speed = int(steps_per_sec)
            if self.unit_mode == "mm":
                eff = self._effective_steps_per_unit()
                if eff > 0.0:
                    self.max_speed_user = float(steps_per_sec) / eff
                    if self._setup_complete:
                        self._send_motion_config()
            elif self.unit_mode == "rev":
                eff = self._effective_steps_per_unit()
                if eff > 0.0:
                    self.max_speed_user = (float(steps_per_sec) / eff) * 60.0
                    if self._setup_complete:
                        self._send_motion_config()

        def set_acceleration(self, steps_per_sec2: int) -> None:
            self.acceleration = int(steps_per_sec2)
            if self.unit_mode == "mm":
                eff = self._effective_steps_per_unit()
                if eff > 0.0:
                    self.max_acceleration_user = float(steps_per_sec2) / eff
                    if self._setup_complete:
                        self._send_motion_config()
            elif self.unit_mode == "rev":
                eff = self._effective_steps_per_unit()
                if eff > 0.0:
                    self.max_acceleration_user = (float(steps_per_sec2) / eff) * 60.0
                    if self._setup_complete:
                        self._send_motion_config()

        def set_resolution(self, steps_per_rev: int) -> None:
            self.steps_per_revolution = int(steps_per_rev)
            if self._setup_complete and self.unit_mode == "rev":
                self._send_motion_config()

        def set_steps_per_mm(self, steps_per_mm: float) -> None:
            divisor = float(256 if self.microstep_div == 256 else self.microstep_div)
            self.steps_per_mm = float(steps_per_mm)
            self.full_steps_per_mm = float(steps_per_mm) / max(divisor, 1.0)
            self.unit_mode = "mm"
            if self.max_speed_user is None and self.max_speed > 0:
                self.max_speed_user = float(self.max_speed) / max(float(steps_per_mm), 1.0)
            if self.max_acceleration_user is None and self.acceleration > 0:
                self.max_acceleration_user = float(self.acceleration) / max(float(steps_per_mm), 1.0)
            if self._setup_complete and self.max_speed_user is not None and self.max_acceleration_user is not None:
                self._send_motion_config()

        def set_microstepping(self, divisor: int) -> None:
            self.microstep_div = int(divisor)
            if self._setup_complete:
                # 256 is encoded as 0 on the wire (STSPIN220's max divisor
                # overflows uint8; firmware maps byte 0 back to 256).
                wire_div = 0 if divisor == 256 else (divisor & 0xFF)
                payload = (self.identifier.to_bytes(2, "little")
                           + bytes([wire_div]))
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_STEPPER_SET_MICROSTEP, payload),
                    wait_ack=False,
                )

                if self.unit_mode in ("mm", "rev") and self.max_speed_user is not None and self.max_acceleration_user is not None:
                    self._send_motion_config()

        def set_microstepping_mode(self, mode: "GPIO_Lib.Stepper.MICROSTEPS | str | int") -> None:
            if isinstance(mode, IntEnum):
                self.set_microstepping(int(mode))
                return
            if isinstance(mode, int):
                self.set_microstepping(int(mode))
                return
            mode_key = str(mode).strip().lower()
            if mode_key not in self._MICROSTEP_MODE_TO_DIV:
                valid = ", ".join(sorted(self._MICROSTEP_MODE_TO_DIV.keys()))
                raise ValueError(f"Stepper: unsupported microstepping mode '{mode}'. Valid: {valid}")
            self.set_microstepping(self._MICROSTEP_MODE_TO_DIV[mode_key])

        def set_encoder(self, encoder: "GPIO_Lib.Encoder") -> None:
            self._encoder_ref = encoder
            self._has_encoder  = True
            if self._setup_complete:
                self._send_encoder_params()

        def set_pid(self, kp: float, ki: float, kd: float) -> None:
            payload = (
                self.identifier.to_bytes(2, "little")
                + struct.pack("<f", float(kp))
                + struct.pack("<f", float(ki))
                + struct.pack("<f", float(kd))
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_SET_PID, payload),
                wait_ack=False,
            )

        # ── Setup ─────────────────────────────────────────────────

        def setup(self) -> None:
            if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                raise RuntimeError("Stepper: GPIO_Lib transport not connected")
            for name, pin in (("step_pin", self.step_pin), ("dir_pin", self.dir_pin)):
                if not (0 <= pin <= 0xFF):
                    raise ValueError(f"Stepper: {name} out of range")

            # CREATE
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(
                    CMD_STEPPER_CREATE, self.identifier.to_bytes(2, "little")),
                wait_ack=False)

            # SET_PINS
            self._send_pins()

            # Apply microstep mode before sending any unit-aware motion config.
            if self.microstep_div != 1:
                self.set_microstepping(self.microstep_div)

            # Optional extras
            if self.unit_mode != "none":
                self._send_motion_config()
            if self.direction_inverted:
                self.set_direction(True)
            if self.homing_speed_user is not None and self.homing_acceleration_user is not None:
                self._send_homing_config()
            if self._has_encoder and self._encoder_ref is not None:
                self._send_encoder_params()

            self._setup_complete = True

        def initialize(self) -> None:
            """Run the driver-specific startup sequence (e.g. STSPIN220 SLP toggle)."""
            if not self._setup_complete:
                self.setup()
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(
                    CMD_STEPPER_INIT, self.identifier.to_bytes(2, "little")),
                wait_ack=False)

        # ── Motion ────────────────────────────────────────────────

        def move(self, steps: int, speed: Optional[int] = None,
                 acceleration: Optional[int] = None) -> None:
            """Compatibility wrapper: move by raw microsteps using the configured unit mode."""
            target_position = self._current_position_user_estimate() + self._steps_to_current_units(int(steps))
            self._move_to_current_units(
                target=target_position,
                speed_override=self._steps_per_second_to_current_units(speed),
                accel_override=self._steps_per_second_to_current_units(acceleration),
            )

        def move_to(self, position: int, speed: Optional[int] = None,
                    acceleration: Optional[int] = None) -> None:
            """Compatibility wrapper: move to an absolute raw microstep position using the configured unit mode."""
            self._move_to_current_units(
                target=self._steps_to_current_units(int(position)),
                speed_override=self._steps_per_second_to_current_units(speed),
                accel_override=self._steps_per_second_to_current_units(acceleration),
            )

        def move_to_position_mm(self, position_mm: float,
                    speed: Optional[float] = None,
                    acceleration: Optional[float] = None) -> None:
            """Move to absolute position in millimetres.

            Requires ``set_steps_per_mm()`` to have been configured.
            Optional ``speed`` and ``acceleration`` override the current
            stepper parameters for this move only.
            """
            if self.unit_mode != "mm":
                raise RuntimeError("Stepper: configure_motion_mm() must be called before move_to_position_mm()")
            self._move_to_units(
                unit_mode="mm",
                target=float(position_mm),
                speed_override=None if speed is None else float(speed),
                accel_override=None if acceleration is None else float(acceleration),
            )

        def move_to_position_rev(self, target_rev: float,
                                 speed_override_rpm: Optional[float] = None,
                                 accel_override_rpm_s: Optional[float] = None) -> None:
            if self.unit_mode != "rev":
                raise RuntimeError("Stepper: configure_motion_rev() must be called before move_to_position_rev()")
            self._move_to_units(
                unit_mode="rev",
                target=float(target_rev),
                speed_override=speed_override_rpm,
                accel_override=accel_override_rpm_s,
            )

        def configure_motion_mm(
            self,
            steps_per_mm: float,
            max_speed_mm_s: float,
            max_accel_mm_s2: float,
        ) -> None:
            self.full_steps_per_mm = float(steps_per_mm)
            self.unit_mode = "mm"
            self.max_speed_user = float(max_speed_mm_s)
            self.max_acceleration_user = float(max_accel_mm_s2)
            if self._setup_complete:
                self._send_motion_config()

        def configure_motion_rev(
            self,
            steps_per_rev: int,
            max_speed_rpm: float,
            max_accel_rpm_s: float,
        ) -> None:
            self.steps_per_revolution = int(steps_per_rev)
            self.unit_mode = "rev"
            self.max_speed_user = float(max_speed_rpm)
            self.max_acceleration_user = float(max_accel_rpm_s)
            if self._setup_complete:
                self._send_motion_config()

        def configure_homing(
            self,
            speed_mm_s: float,
            accel_mm_s2: float,
            end_stop_left: Optional[int] = None,
            end_stop_right: Optional[int] = None,
        ) -> None:
            if self.unit_mode == "none":
                raise RuntimeError("Stepper: configure motion before configure_homing()")
            self.homing_speed_user = float(speed_mm_s)
            self.homing_acceleration_user = float(accel_mm_s2)
            self.homing_end_stop_left = None if end_stop_left is None else int(end_stop_left)
            self.homing_end_stop_right = None if end_stop_right is None else int(end_stop_right)
            if self._setup_complete:
                self._send_homing_config()

        def home(self) -> None:
            if not self._setup_complete:
                self.setup()
            payload = self.identifier.to_bytes(2, "little")
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_HOME, payload), wait_ack=False)

        def set_direction(self, invert: bool) -> None:
            self.direction_inverted = bool(invert)
            if not self._setup_complete:
                return
            payload = self.identifier.to_bytes(2, "little") + bytes([1 if invert else 0])
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_SET_DIRECTION, payload), wait_ack=False)

        def set_enable(self, state: bool) -> None:
            self.enable(state)

        def set_position_mm(self, position_mm: float) -> None:
            self.set_current_position_mm(position_mm)

        def set_current_position_mm(self, position_mm: float) -> None:
            if self.unit_mode != "mm":
                raise RuntimeError("Stepper: configure_motion_mm() must be called before set_current_position_mm()")
            self._set_position_units("mm", float(position_mm))

        def set_current_position_rev(self, position_rev: float) -> None:
            if self.unit_mode != "rev":
                raise RuntimeError("Stepper: configure_motion_rev() must be called before set_current_position_rev()")
            self._set_position_units("rev", float(position_rev))

        def move_for_time(self, duration_ms: int, forward: bool = True) -> None:
            raise NotImplementedError("Stepper: move_for_time() was removed from the unit-aware API")

        def stop(self, immediate: bool = False) -> None:
            payload = self.identifier.to_bytes(2, "little") + bytes([1 if immediate else 0])
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_STOP, payload), wait_ack=False)

        def enable(self, state: bool = True) -> None:
            payload = self.identifier.to_bytes(2, "little") + bytes([1 if state else 0])
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_ENABLE, payload), wait_ack=False)

        def clear_fault(self) -> None:
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(
                    CMD_STEPPER_CLEAR_FAULT, self.identifier.to_bytes(2, "little")),
                wait_ack=False)

        # ── Status read ───────────────────────────────────────────

        def get_status(self, timeout: float = 1.0, retries: int = 3, retry_delay: float = 0.02) -> Dict:
            """Return unit-aware motion status plus raw step-domain fields."""
            if not self._setup_complete:
                self.setup()
            attempts = max(int(retries), 1)
            timeout_s = max(float(timeout), 0.05)
            attempt_timeout = timeout_s
            resp = b""

            with self.gpio_lib._resp_cv:
                self.gpio_lib._responses.pop((CMD_STEPPER_GET_STATUS, int(self.identifier)), None)

            for attempt in range(attempts):
                payload = self.identifier.to_bytes(2, "little")
                self.gpio_lib._add_packet_to_send_queue(
                    self.gpio_lib._build_packet(CMD_STEPPER_GET_STATUS, payload), wait_ack=False
                )
                resp = self.gpio_lib._await_response(
                    CMD_STEPPER_GET_STATUS,
                    self.identifier,
                    timeout=attempt_timeout,
                )
                if len(resp) >= 21:
                    break
                if attempt + 1 < attempts:
                    time.sleep(max(float(retry_delay), 0.0))

            if len(resp) < 21:
                raise RuntimeError(
                    "Stepper: invalid status response payload. "
                    f"Got {len(resp)} bytes after {attempts} attempt(s), expected at least 21."
                )
            state_code = resp[0]
            unit_code = resp[1]
            position_user = struct.unpack_from("<f", resp, 2)[0]
            speed_user = struct.unpack_from("<f", resp, 6)[0]
            moving = bool(resp[10])
            fault = bool(resp[11])
            fault_flags = resp[12]
            position_steps = int.from_bytes(resp[13:17], "little", signed=True) if len(resp) >= 17 else 0
            speed_steps = struct.unpack_from("<f", resp, 17)[0] if len(resp) >= 21 else 0.0
            state_name = self._STATUS_CODE_TO_NAME.get(state_code, f"unknown:{state_code}")
            unit_name = self._UNIT_CODE_TO_NAME.get(unit_code, "none")
            result: Dict[str, Any] = {
                "state_code": state_code,
                "state": state_name,
                "unit_mode": unit_name,
                "position": position_user if unit_name != "none" else float(position_steps),
                "speed": speed_user if unit_name != "none" else speed_steps,
                "moving": moving,
                "fault": fault,
                "fault_flags": fault_flags,
                "position_steps": position_steps,
                "speed_steps_per_s": speed_steps,
            }
            if unit_name == "mm":
                result["position_mm"] = position_user
                result["speed_mm_s"] = speed_user
            elif unit_name == "rev":
                result["position_rev"] = position_user
                result["speed_rpm"] = speed_user
            return result

        @property
        def is_moving(self) -> bool:
            status = self.get_status(timeout=0.5)
            return bool(status.get("moving", False))

        # Backward-compat alias
        def read(self, timeout: float = 1.0) -> Dict:
            return self.get_status(timeout=timeout)

        def wait_until_stopped(self, timeout: float = 10.0,
                               poll_interval: float = 0.05) -> Dict:
            """Poll status until motion stops and return the final status."""
            deadline = time.time() + float(timeout)
            last_status: Optional[Dict] = None
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("Stepper: timed out waiting for motion to stop")
                last_status = self.get_status(timeout=min(1.0, max(remaining, 0.05)))
                if not last_status["moving"]:
                    return last_status
                time.sleep(max(0.0, float(poll_interval)))

        def get_current_position(self, timeout: float = 1.0) -> float:
            return float(self.get_status(timeout=timeout)["position"])

        def get_current_speed(self, timeout: float = 1.0) -> float:
            return float(self.get_status(timeout=timeout)["speed"])

        def read_encoder_absolute_position(self, encoder: Optional["GPIO_Lib.Encoder"] = None,
                                           timeout: float = 0.5) -> int:
            """Return the attached encoder's signed absolute position in counts."""
            encoder_ref = encoder if encoder is not None else self._encoder_ref
            if encoder_ref is None:
                raise ValueError("Stepper: no encoder provided or attached")
            enc_data = encoder_ref.read(timeout=timeout)
            return int(enc_data["revolutions"]) * int(encoder_ref.ppr) + int(enc_data["position"])

        def verify_microstepping(self, encoder: Optional["GPIO_Lib.Encoder"] = None,
                                 test_steps: int = 200,
                                 speed: int = 50,
                                 move_timeout: float = 10.0,
                                 read_timeout: float = 0.5,
                                 reset_encoder: bool = True,
                                 return_to_origin: bool = True,
                                 fail_loud: bool = True,
                                 divisor_tolerance: int = 1,
                                 min_count_tolerance: float = 1.0,
                                 relative_count_tolerance: float = 0.20) -> Dict[str, Any]:
            """Estimate the effective microstep divisor from encoder motion."""
            encoder_ref = encoder if encoder is not None else self._encoder_ref
            if encoder_ref is None:
                raise ValueError("Stepper: no encoder provided or attached")
            if int(test_steps) == 0:
                raise ValueError("Stepper: test_steps must be non-zero")
            if int(divisor_tolerance) < 0:
                raise ValueError("Stepper: divisor_tolerance must be >= 0")
            if float(min_count_tolerance) < 0.0:
                raise ValueError("Stepper: min_count_tolerance must be >= 0")
            if float(relative_count_tolerance) < 0.0:
                raise ValueError("Stepper: relative_count_tolerance must be >= 0")

            start_status = self.get_status(timeout=read_timeout)
            start_position = int(start_status["position_steps"])

            if reset_encoder:
                encoder_ref.reset()
                self.gpio_lib.await_send_empty()
                time.sleep(0.05)

            self.move(int(test_steps), speed=int(speed))
            self.wait_until_stopped(timeout=move_timeout)
            encoder_counts = self.read_encoder_absolute_position(encoder_ref, timeout=read_timeout)
            abs_counts = abs(encoder_counts)
            detected_divisor_float = (int(encoder_ref.ppr) / float(abs_counts)) if abs_counts > 0 else 0.0
            detected_divisor = round(detected_divisor_float) if abs_counts > 0 else 0

            if return_to_origin:
                self.move_to(start_position, speed=int(speed))
                self.wait_until_stopped(timeout=move_timeout)

            configured_divisor = int(self.microstep_div)
            expected_counts = 0.0
            if configured_divisor > 0 and int(self.steps_per_revolution) > 0:
                expected_counts = (
                    abs(int(test_steps)) * float(encoder_ref.ppr)
                ) / (float(int(self.steps_per_revolution)) * float(configured_divisor))
            count_error = abs(float(abs_counts) - float(expected_counts))
            count_tolerance = max(float(min_count_tolerance), float(expected_counts) * float(relative_count_tolerance))
            divisor_matches = bool(
                abs(int(detected_divisor) - configured_divisor) <= int(divisor_tolerance)
            )
            count_matches = bool(count_error <= count_tolerance)
            matches = bool(divisor_matches or count_matches)
            result: Dict[str, Any] = {
                "encoder_counts": int(encoder_counts),
                "encoder_counts_abs": int(abs_counts),
                "detected_divisor": int(detected_divisor),
                "detected_divisor_float": float(detected_divisor_float),
                "configured_divisor": configured_divisor,
                "expected_counts_full_step": int(encoder_ref.ppr),
                "expected_counts_at_configured_divisor": float(expected_counts),
                "count_error": float(count_error),
                "count_tolerance": float(count_tolerance),
                "matches_divisor_tolerance": divisor_matches,
                "matches_count_tolerance": count_matches,
                "matches_configured_divisor": matches,
            }
            if fail_loud and not matches:
                raise RuntimeError(
                    "Stepper: microstep verification failed: "
                    f"configured 1/{configured_divisor}, detected about 1/{float(detected_divisor_float):.2f} "
                    f"from {int(encoder_counts)} encoder counts for {int(test_steps)} commanded microsteps "
                    f"(expected about {float(expected_counts):.2f} counts, error {float(count_error):.2f}, "
                    f"tolerance {float(count_tolerance):.2f}, full-step baseline {int(encoder_ref.ppr)})."
                )
            return result

        def auto_orient_encoder(self, encoder: Optional["GPIO_Lib.Encoder"] = None,
                                test_steps: int = 50,
                                speed: int = 400,
                                move_timeout: float = 10.0,
                                read_timeout: float = 0.5,
                                reset_encoder: bool = True,
                                reset_after: bool = True) -> Dict[str, int | bool]:
            """Flip the encoder direction if forward stepper motion counts down."""
            encoder_ref = encoder if encoder is not None else self._encoder_ref
            if encoder_ref is None:
                raise ValueError("Stepper: no encoder provided or attached")
            if int(test_steps) == 0:
                raise ValueError("Stepper: test_steps must be non-zero")

            start_status = self.get_status(timeout=read_timeout)
            start_position = int(start_status["position_steps"])

            if reset_encoder:
                encoder_ref.reset()
                self.gpio_lib.await_send_empty()
                time.sleep(0.05)

            self.move(int(test_steps), speed=int(speed))
            self.wait_until_stopped(timeout=move_timeout)
            encoder_counts = self.read_encoder_absolute_position(encoder_ref, timeout=read_timeout)
            flipped = encoder_counts < 0
            if flipped:
                encoder_ref.flip()
                self.gpio_lib.await_send_empty()
                time.sleep(0.05)

            self.move_to(start_position, speed=int(speed))
            self.wait_until_stopped(timeout=move_timeout)

            if reset_after:
                encoder_ref.reset()
                self.gpio_lib.await_send_empty()
                time.sleep(0.05)

            return {
                "encoder_counts": int(encoder_counts),
                "flipped": bool(flipped),
                "direction_ok": bool(not flipped),
            }

        # ── Private helpers ───────────────────────────────────────

        def _send_pins(self) -> None:
            pin_none = self._PIN_NONE

            def _p(v: Optional[int]) -> int:
                return v & 0xFF if v is not None else pin_none

            sleep_pin = _p(self._sleep_pin) if hasattr(self, "_sleep_pin") else pin_none
            payload = bytes([
                self.identifier & 0xFF,
                (self.identifier >> 8) & 0xFF,
                self.step_pin   & 0xFF,
                self.dir_pin    & 0xFF,
                self._driver_type & 0xFF,
                _p(self.enable_pin),
                _p(self.fault_pin),
                sleep_pin,
                _p(self.m0_pin),
                _p(self.m1_pin),
                _p(self.m2_pin),
            ])
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_SET_PINS, payload), wait_ack=False)

        def _effective_microstep_div(self) -> int:
            return 256 if int(self.microstep_div) == 256 else max(int(self.microstep_div), 1)

        def _effective_steps_per_unit(self) -> float:
            if self.unit_mode == "mm":
                if self.full_steps_per_mm is None:
                    return 0.0
                return float(self.full_steps_per_mm) * float(self._effective_microstep_div())
            if self.unit_mode == "rev":
                return float(self.steps_per_revolution) * float(self._effective_microstep_div())
            return 0.0

        def _steps_to_current_units(self, steps: int) -> float:
            eff = self._effective_steps_per_unit()
            if eff <= 0.0:
                raise RuntimeError("Stepper: configure_motion_mm() or configure_motion_rev() before using raw-step compatibility methods")
            return float(steps) / eff

        def _steps_per_second_to_current_units(self, steps_value: Optional[int]) -> Optional[float]:
            if steps_value is None:
                return None
            eff = self._effective_steps_per_unit()
            if eff <= 0.0:
                raise RuntimeError("Stepper: configure motion before using raw-step compatibility methods")
            if self.unit_mode == "mm":
                return float(steps_value) / eff
            if self.unit_mode == "rev":
                return (float(steps_value) / eff) * 60.0
            return float(steps_value)

        def _current_position_user_estimate(self) -> float:
            status = self.get_status(timeout=0.5)
            return float(status["position"])

        def _move_to_current_units(
            self,
            target: float,
            speed_override: Optional[float],
            accel_override: Optional[float],
        ) -> None:
            if self.unit_mode == "mm":
                self.move_to_position_mm(target, speed=speed_override, acceleration=accel_override)
                return
            if self.unit_mode == "rev":
                self.move_to_position_rev(target, speed_override_rpm=speed_override, accel_override_rpm_s=accel_override)
                return
            raise RuntimeError("Stepper: configure_motion_mm() or configure_motion_rev() before moving")

        def _send_motion_config(self) -> None:
            if self.unit_mode not in ("mm", "rev"):
                raise RuntimeError("Stepper: invalid unit mode for motion configuration")
            if self.max_speed_user is None or self.max_acceleration_user is None:
                raise RuntimeError("Stepper: motion speed and acceleration must be configured")
            steps_per_mm = 0.0 if self.full_steps_per_mm is None else float(self.full_steps_per_mm)
            payload = (
                self.identifier.to_bytes(2, "little")
                + bytes([self._UNIT_NAME_TO_CODE[self.unit_mode]])
                + int(self.steps_per_revolution).to_bytes(2, "little")
                + struct.pack("<f", steps_per_mm)
                + struct.pack("<f", float(self.max_speed_user))
                + struct.pack("<f", float(self.max_acceleration_user))
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_CONFIGURE_MOTION, payload), wait_ack=False)

        def _send_homing_config(self) -> None:
            if self.homing_speed_user is None or self.homing_acceleration_user is None:
                raise RuntimeError("Stepper: homing speed and acceleration must be configured")
            left = self._PIN_NONE if self.homing_end_stop_left is None else int(self.homing_end_stop_left) & 0xFF
            right = self._PIN_NONE if self.homing_end_stop_right is None else int(self.homing_end_stop_right) & 0xFF
            flags = 0x01 | 0x02
            payload = (
                self.identifier.to_bytes(2, "little")
                + struct.pack("<f", float(self.homing_speed_user))
                + struct.pack("<f", float(self.homing_acceleration_user))
                + bytes([left, right, flags])
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_CONFIGURE_HOMING, payload), wait_ack=False)

        def _move_to_units(
            self,
            unit_mode: str,
            target: float,
            speed_override: Optional[float],
            accel_override: Optional[float],
        ) -> None:
            if not self._setup_complete:
                self.setup()
            payload = (
                self.identifier.to_bytes(2, "little")
                + bytes([self._UNIT_NAME_TO_CODE[unit_mode]])
                + struct.pack("<f", float(target))
                + struct.pack("<f", 0.0 if speed_override is None else float(speed_override))
                + struct.pack("<f", 0.0 if accel_override is None else float(accel_override))
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_MOVE_TO_UNITS, payload), wait_ack=False)

        def _set_position_units(self, unit_mode: str, position: float) -> None:
            if not self._setup_complete:
                self.setup()
            payload = (
                self.identifier.to_bytes(2, "little")
                + bytes([self._UNIT_NAME_TO_CODE[unit_mode]])
                + struct.pack("<f", float(position))
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_SET_POSITION_UNITS, payload), wait_ack=False)

        def _send_encoder_params(self) -> None:
            if self._encoder_ref is None:
                return
            payload = (
                self.identifier.to_bytes(2, "little")
                + int(self._encoder_ref.identifier).to_bytes(2, "little")
                + int(self._encoder_ref.ppr).to_bytes(2, "little")
            )
            self.gpio_lib._add_packet_to_send_queue(
                self.gpio_lib._build_packet(CMD_STEPPER_SET_ENCODER, payload), wait_ack=False)

    # ── Stepper driver subclasses (defined here so they can inherit from Stepper) ──

    class _StepperSTSPIN220Impl(Stepper):
        """STSPIN220 stepper driver subclass (accessed as ``gpio_lib.Stepper.StepperSTSPIN220``).

        Adds ``sleep_pin``, ``m0_pin``, ``m1_pin`` for the STSPIN220 IC.
        M2 is shared with the STEP pin and M3 with the DIR pin — the
        firmware handles pin-sharing transparently during mode changes.

        Startup::

            stepper = gpio_lib.Stepper.StepperSTSPIN220(
                gpio_lib,
                step_pin=2, dir_pin=3, enable_pin=4,
                m0_pin=5, m1_pin=6,
                sleep_pin=9, fault_pin=10,
            )
            stepper.setup()
            stepper.set_microstepping(32)
            stepper.initialize()   # SLP-toggle startup sequence
        """

        def __init__(
            self,
            gpio_lib: "GPIO_Lib",
            step_pin: int,
            dir_pin: int,
            enable_pin: Optional[int] = None,
            m0_pin: Optional[int] = None,
            m1_pin: Optional[int] = None,
            sleep_pin: Optional[int] = None,
            fault_pin: Optional[int] = None,
            steps_per_revolution: int = 200,
            max_speed: int = 400,
            acceleration: int = 400,
        ) -> None:
            super().__init__(
                gpio_lib,
                step_pin=step_pin,
                dir_pin=dir_pin,
                enable_pin=enable_pin,
                fault_pin=fault_pin,
                m0_pin=m0_pin,
                m1_pin=m1_pin,
                m2_pin=None,
                steps_per_revolution=steps_per_revolution,
                max_speed=max_speed,
                acceleration=acceleration,
                _driver_type=GPIO_Lib.Stepper.DRIVER_STSPIN220,
            )
            self._sleep_pin = int(sleep_pin) if sleep_pin is not None else None

    class _StepperDRV8825Impl(Stepper):
        """DRV8825 stepper driver subclass (accessed as ``gpio_lib.Stepper.StepperDRV8825``).

        Adds independent ``m0_pin``, ``m1_pin``, ``m2_pin`` mode pins and an
        active-LOW ``fault_pin`` for nFAULT detection.

        Startup::

            stepper = gpio_lib.Stepper.StepperDRV8825(
                gpio_lib,
                step_pin=2, dir_pin=3, enable_pin=4,
                m0_pin=5, m1_pin=6, m2_pin=7, fault_pin=8,
            )
            stepper.setup()
            stepper.set_microstepping(32)
        """

        def __init__(
            self,
            gpio_lib: "GPIO_Lib",
            step_pin: int,
            dir_pin: int,
            enable_pin: Optional[int] = None,
            m0_pin: Optional[int] = None,
            m1_pin: Optional[int] = None,
            m2_pin: Optional[int] = None,
            fault_pin: Optional[int] = None,
            steps_per_revolution: int = 200,
            max_speed: int = 400,
            acceleration: int = 400,
        ) -> None:
            super().__init__(
                gpio_lib,
                step_pin=step_pin,
                dir_pin=dir_pin,
                enable_pin=enable_pin,
                fault_pin=fault_pin,
                m0_pin=m0_pin,
                m1_pin=m1_pin,
                m2_pin=m2_pin,
                steps_per_revolution=steps_per_revolution,
                max_speed=max_speed,
                acceleration=acceleration,
                _driver_type=GPIO_Lib.Stepper.DRIVER_DRV8825,
            )

    # Attach driver subclasses to Stepper for the gpio_lib.Stepper.StepperXxx(…) API
    Stepper.StepperSTSPIN220 = _StepperSTSPIN220Impl  # type: ignore[attr-defined]
    Stepper.StepperDRV8825   = _StepperDRV8825Impl    # type: ignore[attr-defined]

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
                self.gpio_lib._add_packet_to_send_queue(self.gpio_lib._build_packet(CMD_ST7735_CREATE, payload), wait_ack=True)

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
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=True)

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
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=True)

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
                    self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=True, validate=False)

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

        class DisplayUNO_R4_MATRIX:
            """Arduino Uno R4 onboard 12x8 red LED matrix display."""
            
            # Predefined frame IDs (loaded in Arduino LED Matrix library)
            class Frame(IntEnum):
                """Preloaded frames from Arduino library."""
                EMOJI_BASIC = 0x00
                EMOJI_HAPPY = 0x01
                EMOJI_SAD = 0x02
                HEART_BIG = 0x03
                HEART_SMALL = 0x04
                BOOTLOADER_ON = 0x05
                CLOUD_WIFI = 0x06
                BLUETOOTH = 0x07
                DANGER = 0x08
                CHIP = 0x09
                LIKE = 0x0A
                MUSIC_NOTE = 0x0B
                RESISTOR = 0x0C
                UNO = 0x0D
            
            # Animation IDs (loaded in Arduino LED Matrix library)
            class Animation(IntEnum):
                """Preloaded animations from Arduino library."""
                STARTUP = 0x00
                TETRIS_INTRO = 0x01
                ATMEGA = 0x02
                LED_BLINK_HORIZONTAL = 0x03
                LED_BLINK_VERTICAL = 0x04
                ARROWS_COMPASS = 0x05
                AUDIO_WAVEFORM = 0x06
                BATTERY = 0x07
                BOUNCING_BALL = 0x08
                BUG = 0x09
                CHECK = 0x0A
                CLOUD = 0x0B
                DOWNLOAD = 0x0C
                DVD = 0x0D
                HEARTBEAT_LINE = 0x0E
                HEARTBEAT = 0x0F
                INFINITY_LOOP_LOADER = 0x10
                LOAD_CLOCK = 0x11
                LOAD = 0x12
                LOCK = 0x13
                NOTIFICATION = 0x14
                OPENSOURCE = 0x15
                SPINNING_COIN = 0x16
                TETRIS = 0x17
                WIFI_SEARCH = 0x18

            total_instances = 0

            def __init__(self, gpio_lib: GPIO_Lib) -> None:
                """Initialize the Uno R4 LED Matrix display."""
                self.gpio_lib = gpio_lib
                # Only one instance supported (Uno R4 only has one matrix)
                if self.__class__.total_instances > 0:
                    raise RuntimeError("DisplayUNO_R4_MATRIX: Only one instance supported (Uno R4 has one built-in matrix)")
                
                self.identifier = 0  # Fixed identifier for single instance
                self.__class__.total_instances += 1
                self._setup_complete = False
                self._animation_active = False

            def setup(self) -> None:
                """Initialize the matrix display."""
                if not self.gpio_lib._transport or not self.gpio_lib._transport.is_connected:
                    raise RuntimeError("DisplayUNO_R4_MATRIX: GPIO_Lib transport not connected")
                
                # Send create command
                payload = bytes()  # No payload needed for matrix creation (single instance)
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_CREATE, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
                
                self._setup_complete = True

            def clear(self) -> None:
                """Clear the LED matrix (turn off all LEDs)."""
                if not self._setup_complete:
                    self.setup()
                
                payload = bytes()  # No payload for clear
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_CLEAR, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_pixel(self, x: int, y: int, value: bool) -> None:
                """
                Set a single pixel on/off.
                Args:
                    x: X coordinate (0-11)
                    y: Y coordinate (0-7)
                    value: True to turn LED on, False to turn off
                """
                if not self._setup_complete:
                    self.setup()
                
                x = int(x)
                y = int(y)
                if x < 0 or x > 11 or y < 0 or y > 7:
                    raise ValueError("DisplayUNO_R4_MATRIX: pixel coordinates out of range (x: 0-11, y: 0-7)")
                
                # value: 1 for on, 0 for off
                val = 1 if value else 0
                payload = bytes([x, y, val])
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SET_PIXEL, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_text(self, text: str, speed: int = 0) -> None:
                """
                Write text to the matrix display with optional scrolling.
                Args:
                    text: Text to display (UTF-8)
                    speed: Scroll speed in milliseconds (0 = no scrolling, static text)
                """
                # [ ] TODO Teyt implementation broken
                if not self._setup_complete:
                    self.setup()
                
                speed = int(speed)
                if speed < 0 or speed > 255:
                    raise ValueError("DisplayUNO_R4_MATRIX: speed must be 0-255 (milliseconds)")
                
                text_bytes = text.encode('utf-8', errors='replace')
                payload = bytes([speed]) + text_bytes
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_WRITE_TEXT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def show_animation(self, animation: int, speed: int = 1, play: bool = True) -> None:
                """
                Start or stop an animation on the matrix.
                Args:
                    animation: Animation ID (from Animation enum or custom)
                    speed: Animation speed/playback speed (0-255)
                    play: True to play, False to stop
                """
                if not self._setup_complete:
                    self.setup()
                
                animation = int(animation)
                speed = int(speed)
                if speed < 0 or speed > 255:
                    raise ValueError("DisplayUNO_R4_MATRIX: speed must be 0-255")
                
                start_stop = 1 if play else 0
                payload = bytes([start_stop, speed, animation])
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_ANIMATION, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
                
                self._animation_active = play

            def show_frame(self, frame: int) -> None:
                """
                Display a preloaded frame on the matrix.
                Args:
                    frame: Frame ID (from Frame enum)
                """
                # Stop any active animation first
                if self._animation_active:
                    self.show_animation(0, play=False)
                
                # Show the frame as a single frame animation
                self.show_animation(frame, speed=0, play=False)

            def set_animation_frame(self, frame_number: int, bitmap: List[int]) -> None:
                """
                Set a custom animation frame using a simple bitmap.

                The bitmap is a list of 8 integers (one per row y=0..7) where
                each integer encodes 12 columns of data.  Bits are read from LSB
                to MSB (bit0 = x=0).  The host mirrors the image horizontally
                (same logic as ``write_bitmap``) before packaging it for the
                device.  This replaces the previous tuple-based API.

                Args:
                    frame_number: Frame number to set (0-255)
                    bitmap: List of 8 row values (bits).
                """
                if not self._setup_complete:
                    self.setup()

                frame_number = int(frame_number)
                if frame_number < 0 or frame_number > 255:
                    raise ValueError("DisplayUNO_R4_MATRIX: frame_number must be 0-255")

                if not isinstance(bitmap, (list, tuple)):
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must be a list of 8 integers")
                if len(bitmap) != 8:
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must contain exactly 8 rows")

                # build payload by iterating rows and bits
                payload = bytearray([frame_number])
                for y, row_val in enumerate(bitmap):
                    row_val = int(row_val)
                    for x in range(12):
                        if row_val & (1 << x):
                            flipped_x = 11 - x  # horizontal flip matches write_bitmap
                            payload += bytes([flipped_x, y, 1])

                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SET_ANIMATION_FRAME, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def write_bitmap(self, bitmap: List[int]) -> None:
                """
                Write a bitmap directly to the matrix display without storing it.
                The bitmap is displayed immediately and is not stored as a frame.
                This is useful for real-time updates without consuming frame storage.

                The host always mirrors the image horizontally so that bit0/LSB ends
                up at the right side of the display.  This keeps orientation consistent
                with the physical board (left-to-right wiring is reversed).

                Args:
                    bitmap: List of 8 integers, one per row (y=0 to y=7).
                            Each integer represents 12 bits (x=0 to x=11).
                            Bits are read from LSB to MSB (bit 0 = x=0,
                            bit 11 = x=11).  The value is flipped horizontally
                            before being sent to the device.
                            Example: 0b0000000011100000 sets x=4,5,6 after flip.
                """
                if not self._setup_complete:
                    self.setup()

                if not isinstance(bitmap, (list, tuple)):
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must be a list of 8 integers")

                if len(bitmap) != 8:
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must contain exactly 8 rows")

                # Build payload as LED data (x,y,v tuples) with horizontal flip
                payload = bytearray()
                for y, row_val in enumerate(bitmap):
                    row_val = int(row_val)
                    for x in range(12):
                        if row_val & (1 << x):
                            flipped_x = 11 - x
                            payload += bytes([flipped_x, y, 1])

                # Send direct bitmap write command (no frame storage)
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_WRITE_BITMAP_DIRECT, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            # backward compatibility wrapper for legacy tests/api
            def load_frame_data(self, frame_data: bytes | bytearray | List[int]) -> None:
                """
                Backwards-compatible helper matching the old API.  Converts the
                12-byte packed frame into a bitmap and calls :meth:`write_bitmap`.
                """
                # reuse earlier conversion logic from previous implementation
                if isinstance(frame_data, (bytes, bytearray)):
                    if len(frame_data) != 12:
                        raise ValueError("DisplayUNO_R4_MATRIX: frame_data must be exactly 12 bytes")
                    data = bytes(frame_data)
                elif isinstance(frame_data, list):
                    if len(frame_data) == 3:  # three uint32 values
                        data = bytearray()
                        for val in frame_data:
                            data.extend(int(val).to_bytes(4, "little"))
                        data = bytes(data)
                    elif len(frame_data) == 12:
                        data = bytes(frame_data)
                    else:
                        raise ValueError("DisplayUNO_R4_MATRIX: frame_data as list must be 3 uint32 integers or 12 bytes")
                else:
                    raise ValueError("DisplayUNO_R4_MATRIX: frame_data must be bytes or list")

                # unpack to 8-row bitmap
                bitmap = []
                for y in range(8):
                    row_val = 0
                    for x in range(12):
                        bit_pos = y * 12 + x
                        byte_idx = bit_pos // 8
                        bit_idx = bit_pos % 8
                        if data[byte_idx] & (1 << bit_idx):
                            row_val |= (1 << x)
                    bitmap.append(row_val)
                self.write_bitmap(bitmap)

            # ===================================================================
            # Custom frame/animation API (new commands - separate from built-in)
            # ===================================================================

            def set_custom_frame(self, frame_id: int, bitmap: List[int]) -> None:
                """
                Store a custom frame (0-15) that can be displayed later.
                Custom frames use separate storage from built-in frames,
                so they won't interfere with built-in animations.

                Args:
                    frame_id: Frame ID (0-15)
                    bitmap: List of 8 integers, one per row (y=0 to y=7).
                            Each integer represents 12 bits (x=0 to x=11).
                            Bits are read from LSB to MSB (bit 0 = x=0).
                            The bitmap will be flipped horizontally before
                            being sent to the device.
                """
                if not self._setup_complete:
                    self.setup()

                frame_id = int(frame_id)
                if frame_id < 0 or frame_id > 15:
                    raise ValueError("DisplayUNO_R4_MATRIX: frame_id must be 0-15")

                if not isinstance(bitmap, (list, tuple)):
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must be a list of 8 integers")
                if len(bitmap) != 8:
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmap must contain exactly 8 rows")

                # Build payload: frame_id + LED data as x,y,v tuples
                payload = bytearray([frame_id])
                for y, row_val in enumerate(bitmap):
                    row_val = int(row_val)
                    for x in range(12):
                        if row_val & (1 << x):
                            flipped_x = 11 - x  # horizontal flip
                            payload += bytes([flipped_x, y, 1])

                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SET_CUSTOM_FRAME, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def show_custom_frame(self, frame_id: int) -> None:
                """
                Display a previously stored custom frame.

                Args:
                    frame_id: Frame ID (0-15) that was set with set_custom_frame()
                """
                if not self._setup_complete:
                    self.setup()

                frame_id = int(frame_id)
                if frame_id < 0 or frame_id > 15:
                    raise ValueError("DisplayUNO_R4_MATRIX: frame_id must be 0-15")

                payload = bytes([frame_id])
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SHOW_CUSTOM_FRAME, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def set_custom_animation(self, animation_id: int, bitmaps: List[List[int]], loop: bool = True) -> None:
                """
                Store a custom animation (0-3) consisting of multiple frames.
                Custom animations use separate storage from built-in animations.

                Args:
                    animation_id: Animation ID (0-3)
                    bitmaps: List of bitmaps (each bitmap is a list of 8 integers).
                             Maximum 8 frames per animation.
                    loop: If True, animation loops continuously; if False, plays once.
                """
                if not self._setup_complete:
                    self.setup()

                animation_id = int(animation_id)
                if animation_id < 0 or animation_id > 3:
                    raise ValueError("DisplayUNO_R4_MATRIX: animation_id must be 0-3")

                if not isinstance(bitmaps, list) or len(bitmaps) == 0:
                    raise ValueError("DisplayUNO_R4_MATRIX: bitmaps must be a non-empty list")
                if len(bitmaps) > 8:
                    raise ValueError("DisplayUNO_R4_MATRIX: maximum 8 frames per animation")

                # Validate all bitmaps
                for i, bitmap in enumerate(bitmaps):
                    if not isinstance(bitmap, (list, tuple)):
                        raise ValueError(f"DisplayUNO_R4_MATRIX: bitmap {i} must be a list of 8 integers")
                    if len(bitmap) != 8:
                        raise ValueError(f"DisplayUNO_R4_MATRIX: bitmap {i} must contain exactly 8 rows")

                # Build payload: animation_id, num_frames, loop, frame_data
                num_frames = len(bitmaps)
                loop_byte = 1 if loop else 0
                payload = bytearray([animation_id, num_frames, loop_byte])

                # For each frame, convert to 12-byte packed format
                for bitmap in bitmaps:
                    frame_data = bytearray(12)  # 12 bytes = 96 bits
                    for y, row_val in enumerate(bitmap):
                        row_val = int(row_val)
                        for x in range(12):
                            if row_val & (1 << x):
                                flipped_x = 11 - x  # horizontal flip
                                # Pack as y*12 + x bit position
                                bit_pos = y * 12 + flipped_x
                                byte_idx = bit_pos // 8
                                bit_idx = bit_pos % 8
                                frame_data[byte_idx] |= (1 << bit_idx)
                    payload.extend(frame_data)

                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SET_CUSTOM_ANIMATION, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)

            def show_custom_animation(self, animation_id: int, speed: int = 10) -> None:
                """
                Play a previously stored custom animation.

                Args:
                    animation_id: Animation ID (0-3) that was set with set_custom_animation()
                    speed: Animation speed in units of 10ms per frame.
                           For example: speed=10 means 100ms per frame (10 fps),
                                       speed=5 means 50ms per frame (20 fps).
                           Valid range: 1-255.
                """
                if not self._setup_complete:
                    self.setup()

                animation_id = int(animation_id)
                if animation_id < 0 or animation_id > 3:
                    raise ValueError("DisplayUNO_R4_MATRIX: animation_id must be 0-3")

                speed = int(speed)
                if speed < 1 or speed > 255:
                    raise ValueError("DisplayUNO_R4_MATRIX: speed must be 1-255")

                payload = bytes([animation_id, speed])
                packet = self.gpio_lib._build_packet(CMD_UNO_R4_MATRIX_SHOW_CUSTOM_ANIMATION, payload)
                self.gpio_lib._add_packet_to_send_queue(packet, wait_ack=False)
                
                self._animation_active = True









































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

    def digitalRead(self, pin: int | str) -> bool:
        return self.digital_read(pin)

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
                self._raise_pending_exception()
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
            # Decode the last-sent packet to show which command triggered the error
            last = self.last_send_data
            last_cmd_str = "unknown"
            if last and len(last) >= 4 and last[0] == CMD_START_BYTE:
                last_cmd_val = int(last[1]) | (int(last[2]) << 8)
                last_cmd_str = _cmd_name(last_cmd_val)
            errmsg = (
                f"device error in response to {last_cmd_str}"
                + (f": {payload!r}" if payload else "")
            )
            self.log_debug_message(f"device: ERROR — {errmsg}")
            if self.raise_on_CMD_DEVICE_ERROR:
                self._set_pending_exception(RuntimeError(errmsg))
            return

        # UART/I2C/SPI/Encoder/Stepper read responses: payload = id(2) + data
        if cmd in (
            CMD_UART_READ,
            CMD_I2C_READ,
            CMD_I2C_WRITE_READ,
            CMD_I2C_FULL_ADDRESS_SCAN,
            CMD_SPI_READ,
            CMD_ENCODER_READ,
            CMD_STEPPER_GET_STATUS,
        ) and len(payload) >= 2:
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



