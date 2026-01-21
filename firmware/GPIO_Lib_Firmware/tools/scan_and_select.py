#!/usr/bin/env python3
"""
Simple device scanner that lists serial ports and lets the user pick a target
platform. It then updates `platformio.ini`'s `default_envs` entry to the chosen
environment so PlatformIO will build for that target by default.

Usage: python tools/scan_and_select.py

This script requires `pyserial` for listing serial ports.
"""
import os
import sys
import re
import argparse
import shutil

try:
    import serial.tools.list_ports
except Exception:
    print("pyserial not installed. Install with: pip install pyserial")
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INI_PATH = os.path.join(ROOT, 'platformio.ini')

ENV_MAP = {
    'uno': 'uno',
    'esp32': 'esp32',
    'stm32': 'stm32',
}


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    out = []
    for p in ports:
        out.append({'device': p.device, 'desc': p.description or '', 'hwid': p.hwid or ''})
    return out


def detect_board_type_from_port(port: dict) -> str | None:
    """Try to heuristically detect board type from port description/hwid.
    Returns one of 'uno', 'esp32', 'stm32' or None if unknown.
    """
    desc = (port.get('desc') or '').lower()
    hwid = (port.get('hwid') or '').upper()

    # quick checks from description
    if 'esp32' in desc or 'espressif' in desc or 'esp32' in hwid.lower():
        return 'esp32'
    if 'arduino' in desc or 'uno' in desc:
        return 'uno'
    if 'stlink' in desc or 'stmicro' in desc or 'stm32' in desc:
        return 'stm32'

    # try parse VID:PID from hwid (common formats)
    m = None
    import re
    m = re.search(r'VID[:_ ]?[:=]?([0-9A-F]{4})[: ]?[:=]?([0-9A-F]{4})', hwid)
    if not m:
        m = re.search(r'([0-9A-F]{4}):([0-9A-F]{4})', hwid)
    if m:
        vid = m.group(1)
        pid = m.group(2)
        # Arduino official UNO VID/PID (varies) and common USB-serial chips
        if (vid, pid) in [('2341', '0043'), ('2A03', '0043')]:
            return 'uno'
        # CH340 (common clone) -> treat as UNO-compatible serial
        if (vid, pid) in [('1A86', '7523')]:
            return 'uno'

        # Some devkits (including certain ESP32 Pico D4 / CH340 variants)
        # present with VID:PID 1A86:55D3. Map that to 'esp32' so the
        # ENV_MAP -> 'esp32dev' mapping is applied consistently later.
        if (vid, pid) in [('1A86', '55D3')]:
            return 'esp32'

        # CP210x / Silicon Labs / generic serial - ambiguous, prefer UNO
        if vid == '10C4' and pid == 'EA60':
            # often used by ESP32 devkits and CP210x devices; use desc to disambiguate
            if 'esp32' in desc:
                return 'esp32'
            return 'uno'
        # FTDI -> often used with older Arduino variants
        if (vid, pid) in [('0403', '6001')]:
            return 'uno'
        # STMicro VID (e.g., STM32 boards) - treat as stm32
        if vid == '0483':
            return 'stm32'

    return None


def choose(ports, assume_yes: bool = False):
    print('Detected serial ports:')
    for i, p in enumerate(ports):
        print(f"  [{i}] {p['device']} - {p['desc']} ({p['hwid']})")
    print('')
    # automatic mode: try to detect across all ports and pick first confident match
    if assume_yes:
        for p in ports:
            guessed = detect_board_type_from_port(p)
            if guessed:
                print(f"Auto-detected {p['device']} -> {guessed}")
                return p['device'], guessed
        # No confident detection in non-interactive mode: treat as an error so
        # callers (for example a PlatformIO pre-build hook) can abort the build
        # instead of silently defaulting to a different environment.
        print('Error: no supported board detected on any serial port.')
        return None, None

    # interactive/manual mode
    # If only one port exists, attempt auto-detection and ask for confirmation
    dev = None
    if len(ports) == 1:
        guessed = detect_board_type_from_port(ports[0])
        if guessed:
            print(f"Auto-detected board type '{guessed}' for port {ports[0]['device']}")
            yn = input('Use this selection? [Y/n] ').strip().lower()
            if yn in ('', 'y', 'yes'):
                dev = ports[0]['device']
                return dev, guessed
    print('If your board is connected by USB-to-serial pick its index above, press Enter to skip, or type "a" to auto-detect from listed ports.')
    s = input('index|a> ').strip()
    if s == 'a':
        # attempt auto-detect across ports; prefer the first confident match
        for p in ports:
            guessed = detect_board_type_from_port(p)
            if guessed:
                print(f"Auto-detected {p['device']} -> {guessed}")
                yn = input('Use this selection? [Y/n] ').strip().lower()
                if yn in ('', 'y', 'yes'):
                    return p['device'], guessed
        print('No confident auto-detection. Falling back to manual selection.')
        s = input('index> ').strip()
    if s != '':
        try:
            idx = int(s)
            dev = ports[idx]['device']
        except Exception:
            print('invalid selection')
            sys.exit(1)
    # choose target platform
    print('\nSelect target board type:')
    types = ['uno', 'esp32', 'stm32']
    for i, t in enumerate(types):
        print(f'  [{i}] {t}')
    s = input('type> ').strip()
    try:
        t = types[int(s)] if s != '' else 'uno'
    except Exception:
        print('invalid type, defaulting to uno')
        t = 'uno'
    return dev, t


def update_ini(target_env, upload_port: str | None = None):
    if not os.path.isfile(INI_PATH):
        print('platformio.ini not found at', INI_PATH)
        return False
    with open(INI_PATH, 'r', encoding='utf-8') as f:
        txt = f.read()
    # replace or add default_envs line at top
    if re.search(r'^default_envs\s*=.*$', txt, flags=re.M):
        txt = re.sub(r'^default_envs\s*=.*$', f'default_envs = {target_env}', txt, flags=re.M)
    else:
        txt = f'default_envs = {target_env}\n\n' + txt
    # set or replace a top-level upload_port if provided
    if upload_port:
        if re.search(r'^upload_port\s*=.*$', txt, flags=re.M):
            txt = re.sub(r'^upload_port\s*=.*$', f'upload_port = {upload_port}', txt, flags=re.M)
        else:
            # insert upload_port after default_envs (top of file)
            txt = txt.replace(f'default_envs = {target_env}\n\n', f'default_envs = {target_env}\nupload_port = {upload_port}\n\n')
    with open(INI_PATH, 'w', encoding='utf-8') as f:
        f.write(txt)
    print('platformio.ini updated: default_envs =', target_env)
    if upload_port:
        print('platformio.ini updated: upload_port =', upload_port)
    return True


def main():
    parser = argparse.ArgumentParser(description='Scan serial ports and select PlatformIO env')
    parser.add_argument('--yes', '-y', action='store_true', help='(deprecated) auto-accept detected matches and run non-interactively')
    parser.add_argument('--manual', '-m', action='store_true', help='run in manual/interactive mode (disable auto-detect)')
    args = parser.parse_args()

    # default: fully automatic detection; use --manual / -m to force interactive
    if args.manual:
        assume_yes = False
    else:
        # backward compatibility: if --yes specified, prefer that, otherwise default to True
        assume_yes = True

    ports = list_ports()
    dev, typ = choose(ports, assume_yes=assume_yes)
    print('\nSelected:', dev, typ)

    # If no board was detected in non-interactive mode, abort so build/upload
    # actions that depend on a physical device are not run silently.
    if typ is None:
        print('Aborting: no device type detected.')
        sys.exit(2)

    env = ENV_MAP.get(typ, 'uno')
    # backup platformio.ini before editing
    if os.path.isfile(INI_PATH):
        bak = INI_PATH + '.bak'
        try:
            shutil.copyfile(INI_PATH, bak)
            print('Backup written to', bak)
        except Exception as e:
            print('Warning: could not write backup:', e)

    ok = update_ini(env, upload_port=dev)
    if not ok:
        sys.exit(1)
    if dev:
        print('You may wish to also configure upload_port in platformio.ini or pass -p when uploading.')


if __name__ == '__main__':
    main()
