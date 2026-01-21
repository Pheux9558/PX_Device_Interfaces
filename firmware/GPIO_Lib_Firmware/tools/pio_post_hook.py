
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

# Register this function to run after the "upload" action.
env.AddPostAction("upload", after_upload)  # type: ignore

# Keep a visible message when run as a plain post: extra_script as well.
print("POST_HOOK (registered)")


# TODO print potput from test script in PlatformIO logs
