#!/usr/bin/env python3
"""
Automated flag testing script - directly modifies platformio.ini and builds.
"""
import os
import subprocess
import time

ROOT = os.path.abspath(os.path.dirname(__file__))
INI_PATH = os.path.join(ROOT, 'platformio.ini')

BASE_CONFIG = '''[platformio]
default_envs = device

[env]
extra_scripts = pre:tools/pio_pre_hook.py, post:tools/pio_post_hook.py
{lib_deps}
lib_extra_dirs = lib

[env:device]
platform = espressif32
board = lilygo-t-display-s3
framework = arduino
upload_port = /dev/ttyACM0
upload_speed = 921600
monitor_speed = 921600
build_flags = 
\t-DBOARD=ESP32_T_DONGLE_S3
\t-DARDUINO_USB_MODE=1
\t-DARDUINO_USB_CDC_ON_BOOT=1
\t-DDEBUG_USE_FASTLED
\t-DDEBUG_FASTLED_DATA_PIN=40
\t-DDEBUG_FASTLED_CLOCK_PIN=39
\t-DDEBUG_FASTLED_TYPE=FASTLED_TYPE_APA102
\t-DDEBUG_BRIGHTNESS=5
{build_flags}

# Uncomment the line below to run in interactive mode (allows editing build flags during build)
# PIO_INTERACTIVE = 1
'''

def get_lib_deps(flags):
    """Generate lib_deps based on flags."""
    libs = []
    if any(f in flags for f in ['LCD', 'IPS', 'OLED']):
        libs.append('\tadafruit/Adafruit GFX Library@^1.11.9')
    if 'LCD' in flags or 'IPS' in flags:
        libs.append('\tadafruit/Adafruit ST7735 and ST7789 Library@^1.9.3')
    if 'OLED' in flags:
        libs.append('\tadafruit/Adafruit SSD1306@^2.5.7')
    if 'HD44780' in flags or 'AIP31068L' in flags:
        libs.append('\tmarcoschwartz/LiquidCrystal_I2C@^1.1.4')
    
    if libs:
        return 'lib_deps =\n' + '\n'.join(libs)
    return ''

def write_config(flags):
    """Write platformio.ini with given flags."""
    flag_lines = [f'\t-D{f}_SUPPORT' for f in flags]
    lib_deps = get_lib_deps(flags)
    
    config = BASE_CONFIG.format(
        lib_deps=lib_deps,
        build_flags='\n'.join(flag_lines) if flag_lines else '\t-DDEBUG'
    )
    
    with open(INI_PATH, 'w') as f:
        f.write(config)

def build():
    """Run platformio build and return success status."""
    try:
        result = subprocess.run(
            ['pio', 'run', '--target', 'clean'],
            cwd=ROOT,
            capture_output=True,
            timeout=30
        )
        time.sleep(1)
        
        # Set PIO_INTERACTIVE=0 to skip the configurator
        env = os.environ.copy()
        env['PIO_INTERACTIVE'] = '0'
        
        result = subprocess.run(
            ['pio', 'run'],
            cwd=ROOT,
            capture_output=True,
            timeout=120,
            env=env
        )
        return result.returncode == 0, result.stdout.decode(), result.stderr.decode()
    except Exception as e:
        return False, '', str(e)

def test_config(name, flags):
    """Test a configuration and report results."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Flags: {', '.join(flags) if flags else 'None'}")
    print(f"{'='*60}")
    
    write_config(flags)
    success, stdout, stderr = build()
    
    if success:
        # Extract binary size from output
        for line in stdout.split('\n'):
            if 'Flash:' in line and 'used' in line:
                print(f"✓ BUILD SUCCESS - {line.strip()}")
                return True
        print("✓ BUILD SUCCESS (size info not found)")
        return True
    else:
        print("✗ BUILD FAILED")
        # Print last 20 lines of stderr for error details
        error_lines = stderr.split('\n')[-20:]
        print("Error details:")
        for line in error_lines:
            if line.strip():
                print(f"  {line}")
        return False

def main():
    """Run all tests."""
    os.chdir(ROOT)
    
    tests = [
        ("All features enabled", ['DEBUG', 'FASTLED', 'I2C', 'SPI', 'UART', 'LCD', 'HD44780', 'AIP31068L', 'IPS', 'OLED']),
        ("OLED disabled", ['DEBUG', 'FASTLED', 'I2C', 'SPI', 'UART', 'LCD', 'HD44780', 'AIP31068L', 'IPS']),
        ("LCD/IPS disabled", ['DEBUG', 'FASTLED', 'I2C', 'SPI', 'UART', 'HD44780', 'AIP31068L', 'OLED']),
        ("All displays disabled", ['DEBUG', 'FASTLED', 'I2C', 'SPI', 'UART']),
        ("FASTLED disabled", ['DEBUG', 'I2C', 'SPI', 'UART']),
        ("Minimal (core only)", ['I2C', 'SPI', 'UART']),
        ("Debug disabled", ['I2C', 'SPI', 'UART']),
    ]
    
    results = []
    for name, flags in tests:
        success = test_config(name, flags)
        results.append((name, success))
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {len(results)} tests, {sum(1 for _, s in results if s)} passed, {sum(1 for _, s in results if not s)} failed")
    
    # Return non-zero exit code if any test failed
    return 0 if all(s for _, s in results) else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
