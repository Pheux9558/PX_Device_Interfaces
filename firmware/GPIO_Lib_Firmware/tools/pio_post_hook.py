
Import('env') # type: ignore
import os
import subprocess
import tempfile

def after_upload(source, target, env):
	# Runs after the PlatformIO "upload" target completes.
	print("POST_HOOK: upload finished, running post-hook actions")
	project_dir = env.get('PROJECT_DIR', os.getcwd())
	# Example: run an optional helper script placed in tools/
	script = os.path.join(project_dir, 'tools', 'post_upload_task.py')
	if os.path.exists(script):
		python_cmd = env.get('PYTHON', 'python3')
		try:
			subprocess.check_call([python_cmd, script])
		except Exception as e:
			print("POST_HOOK: failed to run", script, "->", e)
	else:
		print("POST_HOOK: no additional script found at", script)

PRJ_ROOT = os.getcwd()
MODE_FILE = os.path.join(tempfile.gettempdir(), '.pio_configurator_mode')

def rename_build_flag_in_ini(source, target, env):
    """Rename build_flags to build_flags_old in platformio.ini to prevent re-application on subsequent runs.
    
    This is only applied in automatic mode. In interactive mode, the user is actively editing,
    so we don't rename to allow fresh re-configuration if needed.
    """
    ini_path = os.path.join(PRJ_ROOT, 'platformio.ini')
    if not os.path.isfile(ini_path):
        print('platformio.ini not found for renaming build_flags')
        return
    try:
        with open(ini_path, 'r') as f:
            lines = f.readlines()
        with open(ini_path, 'w') as f:
            for line in lines:
                if line.strip().startswith('build_flags'):
                    f.write(line.replace('build_flags', 'build_flags_old', 1))
                else:
                    f.write(line)
        print('Renamed build_flags to build_flags_old in platformio.ini to prevent re-application.')
    except Exception as e:
        print(f'Failed to rename build_flags in platformio.ini (non-critical): {e}')

def should_rename_flags():
    """Check if we should rename build_flags. Only rename in automatic mode (NOT interactive)."""
    try:
        if os.path.exists(MODE_FILE):
            with open(MODE_FILE, 'r') as f:
                mode = f.read().strip()
                # Only rename if in automatic mode
                return mode == 'automatic'
    except Exception:
        pass
    # Default: don't rename if we can't determine the mode
    return False

# Register post-upload action
env.AddPostAction("upload", after_upload)  # type: ignore

# Only register rename if we're in automatic mode (not interactive)
if should_rename_flags():
    env.AddPostAction("upload", rename_build_flag_in_ini)  # type: ignore
    print("POST_HOOK: build_flags rename enabled (automatic mode)")
else:
    print("POST_HOOK: build_flags rename disabled (interactive or unknown mode)")

# Keep a visible message when run as a plain post: extra_script as well.
print("POST_HOOK (registered)")


# TODO print potput from test script in PlatformIO logs
