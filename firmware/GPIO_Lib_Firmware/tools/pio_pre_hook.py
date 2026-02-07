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

# Apply build_flags from the freshly written platformio.ini into the current SCons env
# so that edits made via the scanner take effect immediately for this build/upload.
# Supports -D (defines) and -I (include paths). Other flags are appended to CCFLAGS.
def apply_build_flags_to_env():
    ini_path = os.path.join(PRJ_ROOT, 'platformio.ini')
    bf = None
    if os.path.isfile(ini_path):
        with open(ini_path, 'r') as f:
            for line in f:
                if line.strip().startswith('build_flags'):
                    # strip leading 'build_flags =' and surrounding whitespace/quotes
                    _, rhs = line.split('=', 1)
                    bf = rhs.strip().strip('"').strip("'")
                    break
    if not bf:
        print('No build_flags found in platformio.ini; nothing to apply')
        return
    print(f'Applying build flags to current env: {bf}')
    import shlex
    try:
        tokens = shlex.split(bf)
    except Exception:
        tokens = bf.split()

    # Delegate parsing to a helper so it can be unit-tested outside of PlatformIO.
    def parse_build_flags(tokens: list[str], risky_macros: set[str] = { 'GPIO' }):
        defs_local = []
        includes_local = []
        other_local = []
        for tok in tokens:
            # Skip metadata tokens like NAME=VALUE (e.g., BOARD=esp32) — they should not be
            # applied to the compiler or linker as flags or libraries.
            if '=' in tok and not tok.startswith('-D'):
                continue
            if tok.startswith('-D'):
                v = tok[2:]
                name = v.split('=', 1)[0]
                # Skip if this define is known to be risky
                if name.upper() in risky_macros:
                    print(f"Skipping risky define: {tok}")
                    continue
                if '=' in v:
                    name, val = v.split('=', 1)
                    defs_local.append((name, val))
                else:
                    defs_local.append(v)
            elif tok.startswith('-I'):
                includes_local.append(tok[2:])
            else:
                # Skip bare risky tokens as well
                if tok.upper() in risky_macros:
                    print(f"Skipping risky token: {tok}")
                    continue
                other_local.append(tok)
        return defs_local, includes_local, other_local

    defs, includes, other = parse_build_flags(tokens)

    try:
        if defs:
            env.AppendUnique(CPPDEFINES=defs)
        if includes:
            env.AppendUnique(CPPPATH=includes)
        if other:
            env.AppendUnique(CCFLAGS=other)
        print('Build flags applied to env.')
    except Exception as e:
        print(f'Failed to apply build flags to env (non-critical): {e}')

apply_build_flags_to_env()


print('Configuration updated. Continuing PlatformIO action...')
time.sleep(2)  # slight delay to ensure output order in PlatformIO logs
print("\n" * 4)
