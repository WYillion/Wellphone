import subprocess, time, os, sys, json

env = os.environ.copy()
env['ADB'] = r'D:\Documents\AI learning\Wellphone\.tools\platform-tools\adb.exe'
env['ANDROID_ADB_SERVER_PORT'] = '5038'

proc = subprocess.Popen(
    [r'D:\Documents\AI learning\Wellphone\.tools\scrcpy-win64-v4.1\scrcpy.exe',
     '-s', '192.168.1.101:42883',
     '--new-display=1080x1920',
     '--no-audio',
     '--stay-awake'],
    env=env,
    stdout=open('scrcpy_log.txt', 'w'),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0,
)

time.sleep(7)

if proc.poll() is None:
    with open('scrcpy_pid.txt', 'w') as f:
        f.write(str(proc.pid))
    print(f"OK: scrcpy running, PID={proc.pid}")
else:
    with open('scrcpy_log.txt', 'r') as f:
        log = f.read()
    print(f"FAIL: scrcpy exited code={proc.returncode}")
    print(log[-2000:])
