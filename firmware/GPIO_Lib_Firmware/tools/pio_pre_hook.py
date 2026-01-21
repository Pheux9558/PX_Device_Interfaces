#!/usr/bin/env python3
"""
PlatformIO extra script wrapper that runs the scanner before build/upload.
If the scanner fails to find a device (exits non-zero), this script will
exit with a non-zero code to abort the PlatformIO action.

This script is referenced in `platformio.ini` via `extra_scripts = pre:...`.
"""
Import('env') # type: ignore

import os
import sys
import subprocess
import time

# PlatformIO executes extra scripts without a __file__ variable; assume the
# current working directory is the project root when invoked by PlatformIO.
PRJ_ROOT = os.getcwd()
SCANNER = os.path.join(PRJ_ROOT, 'tools', 'scan_or_select.py')

if not os.path.isfile(SCANNER):
    print('scan_or_select.py not found at', SCANNER)
    sys.exit(1)
# Decide interactive vs non-interactive execution.
# If running in a TTY (or user set PIO_INTERACTIVE=1) run interactively
# so the scanner can prompt the user. Otherwise run with --yes to be
# non-interactive (suitable for CI or background tasks).
interactive_requested = os.environ.get('PIO_INTERACTIVE') == '1' or sys.stdin.isatty()
try:
    if interactive_requested:
        # Run in interactive mode (scanner will prompt the user)
        ret = subprocess.call([sys.executable, SCANNER])
        if ret != 0:
            print('Scanner returned non-zero. Aborting PlatformIO action.')
            sys.exit(ret)
    else:
        # Non-interactive / automated environment: force yes
        subprocess.check_call([sys.executable, SCANNER, '--yes'])
except subprocess.CalledProcessError as e:
    print('Scanner failed (no device detected or error). Aborting PlatformIO action.')
    sys.exit(e.returncode)
except Exception as e:
    print('Failed to run scanner:', e)
    print('If you expected interactive prompts, run PlatformIO from a terminal or set PIO_INTERACTIVE=1')
    sys.exit(1)

# If we reach here the scanner updated platformio.ini successfully.
print('Scanner completed successfully.')

# Reset MCU by toggling DTR to clear bootloader entry for avrdude
# The scanner may have left the device in a state that prevents avrdude sync
# This brief DTR toggle ensures the bootloader is cleanly re-entered
def reset_device_for_upload():
    """Toggle DTR on the detected upload port to safely reset the MCU."""
    try:
        import serial
        # Read the upload port from platformio.ini
        ini_path = os.path.join(PRJ_ROOT, 'platformio.ini')
        upload_port = None
        if os.path.isfile(ini_path):
            with open(ini_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('upload_port'):
                        upload_port = line.split('=', 1)[1].strip()
                        break
        if upload_port:
            print(f'Resetting device on {upload_port} for upload...')
            s = serial.Serial(upload_port, 115200)
            s.setDTR(False)
            time.sleep(0.05)
            s.setDTR(True)
            s.close()
            time.sleep(0.3)  # wait for MCU to enter bootloader
        else:
            print('Warning: upload_port not found in platformio.ini; skipping DTR reset')
    except Exception as e:
        print(f'DTR reset failed (non-critical): {e}')

reset_device_for_upload()

print('Configuration updated. Continuing PlatformIO action...')
time.sleep(2)  # slight delay to ensure output order in PlatformIO logs
print("\n" * 4)
