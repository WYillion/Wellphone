import subprocess, time, os, sys

env = os.environ.copy()
env['ADB'] = r'D:\Documents\AI learning\Wellphone\.tools\platform-tools\adb.exe'
env['ANDROID_ADB_SERVER_PORT'] = '5038'

proc = subprocess.Popen(
    [r'D:\Documents\AI learning\Wellphone\.tools\scrcpy-win64-v4.1\scrcpy.exe',
     '-s', '192.168.1.101:42883',
     '--new-display=1080x1920',
     '--start-app=com.android.settings',
     '--display-ime-policy=local',
     '--no-audio',
     '--stay-awake',
     '--no-playback',
     '--record=test_vd6.mp4',
     '--record-format=mp4'],
    env=env,
    stdout=open('scrcpy_vd6_log.txt', 'w'),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0,
)

time.sleep(8)

if proc.poll() is None:
    with open('scrcpy_pid2.txt', 'w') as f:
        f.write(str(proc.pid))
    print(f"OK: second scrcpy running, PID={proc.pid}")
else:
    with open('scrcpy_vd6_log.txt', 'r') as f:
        log = f.read()
    print(f"FAIL: second scrcpy exited code={proc.returncode}")
    print(log[-2000:])
