# Debug Module

## Purpose
Provides visual heartbeat indication via LED for debugging firmware operation. The LED blinks/cycles in sync with the main loop to confirm the firmware is running.

## Features
- **Non-blocking**: Uses internal timing, doesn't interfere with main loop
- **Auto-detection**: Automatically selects GPIO or FastLED based on board
- **Configurable**: LED pin can be overridden via build flags
- **Low overhead**: Only active when `-DDEBUG` build flag is set

## Usage

### Enable Debug Heartbeat
Add `-DDEBUG` to your `build_flags` in `platformio.ini`:

```ini
build_flags = -DDEBUG
```

### GPIO Boards (Default)
Uses `LED_BUILTIN` by default. To use a different pin:

```ini
build_flags = -DDEBUG -DDEBUG_LED_PIN=13
```

### FastLED/NeoPixel Boards
For boards with onboard WS2812/NeoPixel (like T-Dongle-S3):
- Automatically detected and enabled
- Cycles through Red → Green → Blue colors
- Requires `-DFASTLED_SUPPORT` flag

**Note**: WS2812 bit-banging is not yet fully implemented. For full support, add Adafruit NeoPixel library:

```ini
lib_deps = 
    adafruit/Adafruit NeoPixel@^1.10.0
```

## API

### Initialization
```cpp
void debug_init();
```
Call once in `setup()` to configure LED and register DEBUG flag.

### Heartbeat
```cpp
void debug_heartbeat();
```
Call every loop iteration. Internally manages timing (1 second intervals).

## Board Support

| Board Type | LED Control | Heartbeat Pattern |
|-----------|-------------|-------------------|
| Arduino Uno/Nano | GPIO (LED_BUILTIN) | Toggle On/Off |
| ESP32 DevKit | GPIO (LED_BUILTIN) | Toggle On/Off |
| T-Dongle-S3 | WS2812 NeoPixel | RGB Color Cycle |
| Custom | GPIO (DEBUG_LED_PIN) | Toggle On/Off |

## Module Registration
Registers `"DEBUG"` flag in the modules system, visible via `CMD_FIRMWARE_BUILD_FLAGS` command.

## Implementation Notes
- Heartbeat interval: 1000ms per state change
- FastLED integration uses dedicated instance ID `0xFFF0`
- When DEBUG not defined, all functions compile to empty stubs (zero overhead)

## Future Improvements
- [ ] Add WS2812 bit-banging implementation
- [ ] Support variable heartbeat rate
- [ ] Add heartbeat patterns (fast blink, slow pulse, etc.)
- [ ] Integrate with Adafruit NeoPixel library option
