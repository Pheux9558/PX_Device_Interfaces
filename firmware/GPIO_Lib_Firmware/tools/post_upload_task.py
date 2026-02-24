
# Read platforio.ini and extract default_envs entry. Run blink_pin_configured.py with default_envs name
import os
import tempfile
import time
import subprocess

print("POST HOOK: starting post-upload task")



# remove lock file on exit to allow future runs
def cleanup():
    print("POST HOOK: cleaning up lock file")
    LOCK_FILE = os.path.join(tempfile.gettempdir(), '.pio_configurator_lock')
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

import atexit
# atexit.register(cleanup)


def run_blink_example_for_env(env_name: str):
    """Run the blink_pin_configured.py example with parameters based on the environment name."""
    print("POST HOOK: waiting for device to settle...")
    time.sleep(1)  # slight delay to ensure device is ready after upload
    repo_root = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
    example_rel = os.path.join('px_device_interfaces', 'examples', 'blink_pin_configured.py')
    example_path = os.path.join(repo_root, example_rel)

    if not os.path.exists(example_path):
        print("POST HOOK: example not found at", example_path)
        return

    if env_name == 'esp32':
        cmd = ['python3', example_path, '--pin', '10', '--count', '5', '--on-ms', '0.05', '--off-ms', '0.1', '--invert']
    elif env_name == 'device':
        cmd = ['python3', example_path, '--pin', '10', '--count', '5', '--on-ms', '0.05', '--off-ms', '0.1', '--invert']
    elif env_name == 'uno':
        cmd = ['python3', example_path, '--pin', '13', '--count', '2', '--on-ms', '0.05', '--off-ms', '0.1']
    else:
        print('POST HOOK: no actions defined for env', env_name)
        return

    print('POST HOOK: invoking subprocess:', ' '.join(cmd))
    subprocess.run(cmd)
    print("POST HOOK: completed post-upload task for env", env_name)


if False:  # set to True to enable running the example after upload
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
    run_blink_example_for_env(default_envs)
else:
    print("POST HOOK: example execution disabled (set to True to enable)")