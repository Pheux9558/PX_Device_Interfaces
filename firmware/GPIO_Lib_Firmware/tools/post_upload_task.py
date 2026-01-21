

# Read platforio.ini and extract default_envs entry. Run blink_pin_configured.py with default_envs name
import os
import time
import subprocess

print("POST HOOK: starting post-upload task")
print("POST HOOK: waiting for device to settle...")
time.sleep(1)  # slight delay to ensure device is ready after upload

# Read platformio.ini (in the current working directory, which is the project dir)
default_envs = None
ini_path = os.path.join(os.getcwd(), 'platformio.ini')
print("POST HOOK: reading", ini_path)
if not os.path.exists(ini_path):
    print("POST HOOK: platformio.ini not found at", ini_path)
    exit(1)

with open(ini_path, 'r') as f:
    for line in f:
        if line.strip().startswith('default_envs'):
            default_envs = line.split('=')[1].strip()
            break

if default_envs is None:
    print("POST HOOK: default_envs not found in platformio.ini")
    exit(1)

print("POST HOOK: default_envs =", default_envs)

# The firmware project lives in firmware/GPIO_Lib_Firmware; the repository root is the parent directory.
# Build an absolute path to the repository root and to the example script.
# Find repository root by walking up until we see the top-level `python/` folder.
start = os.path.abspath(os.getcwd())
repo_root = None
cur = start
while True:
    if os.path.isdir(os.path.join(cur, 'python')):
        repo_root = cur
        break
    parent = os.path.dirname(cur)
    if parent == cur:
        break
    cur = parent

if repo_root is None:
    # fallback: assume repo root is two levels up from firmware project
    repo_root = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))

example_rel = os.path.join('python', 'examples', 'blink_pin_configured.py')
example_path = os.path.join(repo_root, example_rel)

if not os.path.exists(example_path):
    print("POST HOOK: example not found at", example_path)
    exit(1)

print("POST HOOK: running", example_path, "for env", default_envs)

if default_envs == 'esp32':
    cmd = ['python3', example_path, '--pin', '10', '--count', '5', '--on-ms', '0.05', '--off-ms', '0.1', '--invert']
elif default_envs == 'uno':
    cmd = ['python3', example_path, '--pin', '13', '--count', '2', '--on-ms', '0.05', '--off-ms', '0.1']
else:
    print('POST HOOK: no actions defined for env', default_envs)
    exit(0)

print('POST HOOK: invoking subprocess:', ' '.join(cmd))
subprocess.run(cmd)
print("POST HOOK: completed post-upload task for env", default_envs)