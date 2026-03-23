#!/bin/bash
# Test script to toggle flags and build

cd "$(dirname "$0")"

echo "=== Test 1: Disable OLED ==="
printf "13\n\n" | python tools/scan_or_select.py -i
sleep 2
echo "Current platformio.ini build_flags:"
grep -A15 "build_flags" platformio.ini
sleep 18
echo "Building..."
pio run 2>&1 | tail -20

echo ""
echo "=== Test 2: Disable LCD and IPS ==="
printf "5\n8\n\n" | python tools/scan_or_select.py -i
sleep 2
echo "Current platformio.ini build_flags:"
grep -A15 "build_flags" platformio.ini
sleep 18
echo "Building..."
pio run 2>&1 | tail -20

echo ""
echo "=== Test 3: Disable all displays (LCD, IPS, OLED, HD44780, AIP31068L) ==="
printf "5\n6\n7\n8\n13\n\n" | python tools/scan_or_select.py -i
sleep 2
echo "Current platformio.ini build_flags:"
grep -A15 "build_flags" platformio.ini
sleep 18
echo "Building..."
pio run 2>&1 | tail -20

echo ""
echo "=== Test 4: Disable FASTLED ==="
printf "1\n\n" | python tools/scan_or_select.py -i
sleep 2
echo "Current platformio.ini build_flags:"
grep -A15 "build_flags" platformio.ini
sleep 18
echo "Building..."
pio run 2>&1 | tail -20

echo ""
echo "=== Test 5: Minimal config (clear all, enable only core: I2C, SPI, UART) ==="
printf "c\n2\n3\n4\n\n" | python tools/scan_or_select.py -i
sleep 2
echo "Current platformio.ini build_flags:"
grep -A15 "build_flags" platformio.ini
sleep 18
echo "Building..."
pio run 2>&1 | tail -20

echo ""
echo "=== All tests complete ==="
