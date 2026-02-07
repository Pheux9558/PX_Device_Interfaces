
Import('env') # type: ignore
import os
import subprocess

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

def rename_build_flag_in_ini(source, target, env):
    """Rename build_flags to build_flags_old in platformio.ini to prevent re-application on subsequent runs."""
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

# Register this function to run after the "upload" action.
env.AddPostAction("upload", after_upload)  # type: ignore
env.AddPostAction("upload", rename_build_flag_in_ini)  # type: ignore

# Keep a visible message when run as a plain post: extra_script as well.
print("POST_HOOK (registered)")


# TODO print potput from test script in PlatformIO logs
