#!/usr/bin/env python3
"""
PlatformIO extra script wrapper that runs the scanner before build/upload.
If the scanner fails to find a device (exits non-zero), this script will
exit with a non-zero code to abort the PlatformIO action.

This script is referenced in `platformio.ini` via `extra_scripts = pre:...`.
"""
import os
import sys
import subprocess
import time

# PlatformIO executes extra scripts without a __file__ variable; assume the
# current working directory is the project root when invoked by PlatformIO.
PRJ_ROOT = os.getcwd()
SCANNER = os.path.join(PRJ_ROOT, 'tools', 'scan_and_select.py')

if not os.path.isfile(SCANNER):
    print('scan_and_select.py not found at', SCANNER)
    sys.exit(1)

# Run non-interactively and require a detected board; the scanner returns
# non-zero when no board was confidently detected in non-interactive mode.
try:
    subprocess.check_call([sys.executable, SCANNER, '--yes'])
except subprocess.CalledProcessError as e:
    print('Scanner failed (no device detected or error). Aborting PlatformIO action.')
    sys.exit(e.returncode)
except Exception as e:
    print('Failed to run scanner:', e)
    sys.exit(1)

# If we reach here the scanner updated platformio.ini successfully.
print('Scanner completed successfully.')

print('Configuration updated. Continuing PlatformIO action...')
time.sleep(2)  # slight delay to ensure output order in PlatformIO logs
print("\n" * 4)
