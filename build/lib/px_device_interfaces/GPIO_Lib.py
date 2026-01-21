from __future__ import annotations

import os
import threading
import time
from typing import Dict, List, Optional

from px_device_interfaces.transports import create_transport_for_device, BaseTransport
from px_device_interfaces.settings_manager import load_connection_settings


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


# Command definition for Touchscreen operations (0x00FX)
CMD_TOUCHSCREEN_CREATE              = 0x00F0 # Create Touchscreen instance, payload: (identifier[2 bytes])
# Command definitions for Touchscreen I2C setup and configuration is not yet defined
CMD_TOUCHSCREEN_SETUP_SPI           = 0x00F2 # Setup Touchscreen SPI, payload: (identifier[2 bytes], spi identifier[2 bytes], cs pin[1 byte], dc pin[1 byte], reset pin[1 byte])
CMD_TOUCHSCREEN_READ_XY             = 0x00F5 # Read touchscreen X,Y coordinates, payload: (identifier[2 bytes]), returns: (x[2 bytes], y[2 bytes], pressed[1 byte])
CMD_TOUCHSCREEN_SAVE_SETTINGS       = 0x00FF # Save Touchscreen settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

# Command definitions for Servo operations (0x010X)
CMD_SERVO_ATTACH                    = 0x0100 # Attach servo to pin
CMD_SERVO_DETACH                    = 0x0101 # Detach servo from pin
CMD_SERVO_WRITE                     = 0x0102 # Write angle to servo


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

# Command definitions for I2C operations (0x021X)
CMD_I2C_CREATE                      = 0x0210 # Create I2C instance, payload: (identifier[2 bytes])
CMD_I2C_SET_FREQUENCY               = 0x0211 # Set I2C frequency, payload: (identifier[2 bytes], frequency[4 bytes])
CMD_I2C_SET_PIN_CLOCK               = 0x0212 # Set I2C clock pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_SET_PIN_DATA                = 0x0213 # Set I2C data pin, payload: (identifier[2 bytes], pin number)
CMD_I2C_READ                        = 0x0214 # I2C read, payload: (identifier[2 bytes], device address[1 byte], length), returns: (data bytes)
CMD_I2C_WRITE                       = 0x0215 # I2C write, payload: (identifier[2 bytes], device address[1 byte], data bytes...)
CMD_I2C_SAVE_SETTINGS               = 0x021F # Save I2C settings to non-volatile memory to create it on startup, payload: (identifier[2 bytes])

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

# Command definitions for bluetooth operations (0x027X)
# [ ] Bluetooth commands can be defined here

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



# endregion Command definitions

# region Return codes from device

# General response codes
CMD_DEVICE_OK                       = 0x1000 # General OK response (e.g. Response to valid commands or acknowledgements for actions)
CMD_DEVICE_ERROR                    = 0x1001 # General ERROR response (e.g. Response to invalid commands or parameters)

# Controll codes
CMD_FIRMWARE_BUILD_FLAGS            = 0xFFFD # Response with build flags, returns: (build flags string in UTF-8)
CMD_FIRMWARE_INFO                   = 0xFFFE # Response with firmware info, returns (name string in UTF-8) # Name of the device configuration
CMD_FIRMWARE_VERSION                = 0xFFFF # Response with firmware version, returns: (major, minor, patch)
# endregion Return codes from device

# region Packet building
def _build_packet(cmd: int, payload: bytes = b"") -> bytes:
    """Build a framed packet for sending."""
    length = len(payload)
    chk = (cmd + length + sum(payload)) & 0xFF
    cmd_bytes = int(cmd).to_bytes(2, "little")
    len_bytes = int(length).to_bytes(2, "little")
    print(f"Building packet: CMD=0x{cmd:04X}, LEN={length}, PAYLOAD={payload.hex()}, CHK=0x{chk:02X}")
    return bytes([CMD_START_BYTE]) + cmd_bytes + len_bytes + payload + bytes([chk])
# endregion Packet building



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


class GPIO_Lib:
    """Binary-protocol GPIO library for Arduino-like controllers.

        - Uses the transport returned by `create_transport_for_device(device_name)`.
        - Provides Arduino-like configuration helpers: `pin_mode()` / `pinMode()`,
            `attach_servo()` and `detach_servo()` to configure pins at runtime.
        - Maintains mirrors for inputs, outputs, servos and an LCD buffer.

    auto_io (bool): when True, writes (digital/analog/servo/lcd) are
      immediately sent to the controller and incoming updates are applied
      automatically. When False, the user must call `sync()` to push and
      pull updates.
    """

    def __init__(self, device_name: str, auto_io: bool = True, debug: bool = False):
        self.device_name = device_name
        self.debug = debug
        self.auto_io = bool(auto_io)
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

        # load settings (ensures device exists)
        self._settings = load_connection_settings(device_name, program="Connection_Organiser")

    # --- lifecycle -------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._transport = create_transport_for_device(self.device_name)
        if not self._transport:
            raise RuntimeError("no transport available")
        # propagate debug flag to transport (so it can print raw hex)
        try:
            setattr(self._transport, "debug", bool(self.debug))
        except Exception:
            pass
        self._transport.connect()
        self._running = True
        # wait for device ready banner (handshake) before starting receiver
        try:
            ok = self._wait_for_ready(timeout=5.0)
            if self.debug:
                print("handshake: ready=" + str(ok))
        except Exception:
            ok = False

        # start receive thread and then configure IO
        self._recv_thread = threading.Thread(target=self._recv_worker, daemon=True)
        self._recv_thread.start()

    def _wait_for_ready(self, timeout: float = 5.0) -> bool:
        """Wait up to `timeout` seconds for a textual `GPIO_READY` banner from device.

        Uses `transport.receive()` (text decode) to look for the banner. Returns
        True if detected, False on timeout.
        """
        if not self._transport or not self._transport.is_connected:
            return False
        end = time.time() + float(timeout)
        if self.debug:
            print("Waiting for device ready banner...")
        while time.time() < end:
            try:
                txt = self._transport.receive(timeout=0.5)
                if not txt:
                    continue
                # surface other debug lines in real-time
                # normalize bytes->str
                if isinstance(txt, (bytes, bytearray)):
                    try:
                        txt = txt.decode(errors="replace")
                    except Exception:
                        txt = str(txt)
                if self.debug:
                    print("device-debug:", txt)
                if "GPIO_READY" in txt or "READY" in txt:
                    return True
            except Exception:
                pass
        return False

    def stop(self) -> None:
        self._running = False
        if self._recv_thread:
            self._recv_thread.join(0.5)
        try:
            if self._transport:
                self._transport.disconnect()
        except Exception:
            pass

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

        # send packet if connected
        if self._transport and self._transport.is_connected:
            try:
                self._transport.send(_build_packet(cmd, payload))
            except Exception:
                if self.debug:
                    print("pin_mode: send failed")

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
                self._transport.send(_build_packet(CMD_SERVO_ATTACH, payload))
            except Exception:
                if self.debug:
                    print("attach_servo: send failed")
        return idx

    def detach_servo(self, index: int) -> None:
        idx = int(index) & 0xFF
        if idx in self.servo_array:
            del self.servo_array[idx]
        try:
            if self._transport and self._transport.is_connected:
                self._transport.send(_build_packet(CMD_SERVO_DETACH, bytes([idx & 0xFF])))
        except Exception:
            if self.debug:
                print("detach_servo: send failed")

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
            self._transport.send(_build_packet(cmd, payload))

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
            self._transport.send(_build_packet(cmd, payload))

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
            self._transport.send(_build_packet(cmd, payload))

    def lcd_write(self, text: str) -> None:
        # simple append model; device is expected to handle display payloads
        self.lcd_lines.append(text)
        if self.auto_io and self._transport and self._transport.is_connected:
            cmd = CMD_LCD_WRITE_TEXT
            b = text.encode(errors="replace")
            self._transport.send(_build_packet(cmd, b))

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
            self._transport.send(_build_packet(cmd, payload))
            time.sleep(0.001)
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
            self._transport.send(_build_packet(cmd, payload))
            time.sleep(0.001)

    # --- internals ------------------------------------------------
    def _recv_worker(self) -> None:
        while self._running:
            try:
                # prefer raw bytes when available
                data = None
                if hasattr(self._transport, "receive_bytes"):
                    data = self._transport.receive_bytes(timeout=0.5)
                if data is None:
                    # fallback to text-mode receive
                    raw_text = self._transport.receive(timeout=0.5)
                    if raw_text is None:
                        continue
                    # raw_text may already be bytes if transport returned bytes;
                    # ensure we have bytes
                    data = raw_text if isinstance(raw_text, (bytes, bytearray)) else str(raw_text).encode()
                if not data:
                    continue
                # Some firmware builds emit plain-text debug lines (CRLF terminated)
                # on the same serial port when compiled with DEBUG. Detect and
                # surface these debug lines to the user, removing them from the
                # byte stream so they don't interfere with binary frame parsing.
                if isinstance(data, (bytes, bytearray)):
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
                                if self.debug:
                                    print("device-debug:", s)
                                # remove the debug line and continue
                                remaining = remaining[idx + term_len :]
                                continue
                        # not a debug line; stop scanning
                        break
                    # whatever remains (possibly empty) is binary and should be parsed
                    if remaining:
                        self._buf.extend(remaining)
                else:
                    # non-bytes (shouldn't happen) — just append
                    self._buf.extend(data)
                while True:
                    res = _parse_frame(self._buf)
                    if not res:
                        break
                    cmd, payload = res
                    self._handle_packet(cmd, payload)
            except Exception:
                time.sleep(0.001)

    def _handle_packet(self, cmd: int, payload: bytes) -> None:
        # handle incoming command frames (device -> host updates)
        # Device-level status
        if cmd == CMD_DEVICE_OK:
            if self.debug:
                print("device: OK")
            self.debug_ok_received += 1
            return
        if cmd == CMD_DEVICE_ERROR:
            if self.debug:
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
            if self.debug:
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
            if self.debug:
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
