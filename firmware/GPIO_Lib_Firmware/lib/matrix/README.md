# Matrix Library for Arduino Uno R4

This library provides firmware support for controlling the onboard 12x8 LED matrix on the Arduino Uno R4 WiFi board.

## Prerequisites

- Arduino Uno R4 WiFi board
- Arduino LED Matrix library (included in Arduino Uno R4 board package)
- ArduinoGraphics library (for text rendering)

## Features

- **Pixel Control**: Set individual LEDs on/off
- **Text Display**: Display static or scrolling text
- **Animations**: Play preloaded animations or custom animation frames
- **Frame Management**: Load and manage animation frames

## Command Set

The matrix module responds to commands in the range 0x0060-0x006F:

- `0x0060`: CREATE - Initialize the matrix display
- `0x0061`: CLEAR - Clear all LEDs
- `0x0062`: SET_PIXEL - Set a single pixel
- `0x0063`: WRITE_TEXT - Write scrolling text
- `0x0064`: ANIMATION - Start/stop animations
- `0x0065`: SET_ANIMATION_FRAME - Set custom animation frame data

## Usage

The matrix module is automatically initialized when the firmware starts on an Uno R4 WiFi board (when `ARDUINO_UNOR4_WIFI` is defined).

## Implementation Notes

- The matrix is 12 columns x 8 rows (96 LEDs total)
- Frame data is stored as 12 bytes (96 bits)
- Animations can be preloaded from the Arduino library or custom
- Text rendering uses the ArduinoGraphics library for cross-platform support
