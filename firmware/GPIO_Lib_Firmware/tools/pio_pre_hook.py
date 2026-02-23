#!/usr/bin/env python3
"""
PlatformIO extra script wrapper that runs the device configurator before build/upload.
Ensures single execution per build session using a lock file.

This script is referenced in `platformio.ini` via `extra_scripts = pre:...`.
"""
Import('env') # type: ignore

import os
import sys
import subprocess
import time
import tempfile

# PlatformIO executes extra scripts without a __file__ variable; assume the
# current working directory is the project root when invoked by PlatformIO.
PRJ_ROOT = os.getcwd()
SCANNER = os.path.join(PRJ_ROOT, 'tools', 'scan_or_select.py')
INI_PATH = os.path.join(PRJ_ROOT, 'platformio.ini')

# Lock file to ensure single execution per build session
# Use a temporary lock that PlatformIO clears between builds
LOCK_FILE = os.path.join(tempfile.gettempdir(), '.pio_configurator_lock')

def acquire_lock():
    """Try to acquire exclusive lock. Returns True if successful."""
    try:
        # If lock exists and is recent (less than 5 seconds old), skip execution
        if os.path.exists(LOCK_FILE):
            age = time.time() - os.path.getmtime(LOCK_FILE)
            if age < 5:
                return False
        
        # Create/update lock file
        with open(LOCK_FILE, 'w') as f:
            f.write(str(time.time()))
        return True
    except Exception:
        # If lock creation fails, proceed anyway
        return True

def release_lock():
    """Release lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

def relock():
    """Recreate lock file to extend validity."""
    release_lock()
    acquire_lock()

def check_ini_interactive_mode() -> bool:
    """Check if PIO_INTERACTIVE is uncommented in platformio.ini."""
    try:
        if not os.path.isfile(INI_PATH):
            return False
        
        with open(INI_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                # Check for uncommented PIO_INTERACTIVE = 1
                if line.startswith('PIO_INTERACTIVE') and '=' in line:
                    # Must be uncommented (not start with #)
                    parts = line.split('=')
                    if len(parts) == 2:
                        value = parts[1].strip()
                        return value == '1'
        return False
    except Exception:
        return False

if not os.path.isfile(SCANNER):
    print('scan_or_select.py not found at', SCANNER)
    sys.exit(1)

# Check if we should skip execution (already ran in this session)
if not acquire_lock():
    print("Configurator already executed in this session. Skipping.")
    sys.exit(0)

try:
    # Detect if running from PlatformIO IDE vs user terminal
    # IDE: PLATFORMIO_IDE env var present OR no terminal
    is_pio_ide = 'PLATFORMIO_IDE' in os.environ or 'TERM' not in os.environ
    
    # Determine interactive mode from environment variable OR INI file
    # Priority: environment variable > INI file, but NOT in IDE to prevent prompts during automated builds
    interactive_from_env = os.environ.get('PIO_INTERACTIVE') == '1'
    interactive_from_ini = check_ini_interactive_mode() and not is_pio_ide
    interactive_requested = (interactive_from_env or interactive_from_ini) and not is_pio_ide
    
    print("Running device configurator...")
    if is_pio_ide:
        print("Detected: PlatformIO IDE (automatic mode only)")
    
    if interactive_requested:
        if interactive_from_env:
            print("Interactive mode enabled (PIO_INTERACTIVE environment variable)")
        else:
            print("Interactive mode enabled (PIO_INTERACTIVE = 1 in platformio.ini)")
        ret = subprocess.call([sys.executable, SCANNER, '-i'])
        if ret != 0:
            print('Configurator returned non-zero. Aborting.')
            sys.exit(ret)
        # After interactive configuration, relock to prevent accidental re-execution in the same session if the user takes too long
        relock()
    else:
        print("Automatic mode (no user prompts)")
        subprocess.check_call([sys.executable, SCANNER])

except subprocess.CalledProcessError as e:
    release_lock()
    print('Configurator failed. Aborting PlatformIO action.')
    sys.exit(e.returncode)
except Exception as e:
    release_lock()
    print(f'Configurator error: {e}')
    sys.exit(1)

print('Configurator completed successfully.')

# Reset MCU by toggling DTR to clear bootloader entry for avrdude
def reset_device_for_upload():
    """Toggle DTR on the detected upload port to safely reset the MCU."""
    try:
        import serial
        upload_port = None
        if os.path.isfile(INI_PATH):
            with open(INI_PATH, 'r') as f:
                for line in f:
                    if line.strip().startswith('upload_port'):
                        upload_port = line.split('=', 1)[1].strip()
                        break
        if upload_port:
            print(f'Resetting device on {upload_port}...')
            s = serial.Serial(upload_port, 115200)
            s.setDTR(False)
            time.sleep(0.05)
            s.setDTR(True)
            s.close()
            time.sleep(0.3)
        else:
            print('Warning: upload_port not found in platformio.ini')
    except Exception as e:
        print(f'DTR reset warning (non-critical): {e}')

reset_device_for_upload()

# Apply build_flags from platformio.ini into the current SCons env
def apply_build_flags_to_env():
    """Read build_flags from INI and apply to SCons environment."""
    bf = None
    if os.path.isfile(INI_PATH):
        with open(INI_PATH, 'r') as f:
            for line in f:
                if line.strip().startswith('build_flags'):
                    _, rhs = line.split('=', 1)
                    bf = rhs.strip().strip('"').strip("'")
                    break
    
    if not bf:
        print('No build_flags found in platformio.ini')
        return
    
    print(f'Applying build flags: {bf}')
    import shlex
    try:
        tokens = shlex.split(bf)
    except Exception:
        tokens = bf.split()

    def parse_build_flags(tokens: list[str], risky_macros: set[str] = {'GPIO'}):
        defs_local = []
        includes_local = []
        other_local = []
        for tok in tokens:
            if '=' in tok and not tok.startswith('-D'):
                continue
            if tok.startswith('-D'):
                v = tok[2:]
                name = v.split('=', 1)[0]
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
        print('Build flags applied to environment.')
    except Exception as e:
        print(f'Warning: Failed to apply flags to env: {e}')

apply_build_flags_to_env()
print('Configuration ready. Continuing PlatformIO action...')
time.sleep(1)



