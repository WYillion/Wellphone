import subprocess, time, os, sys, json

ADB = r'D:\Documents\AI learning\Wellphone\.tools\platform-tools\adb.exe'
SERIAL = '192.168.1.101:42883'
PORT = '5038'

env = os.environ.copy()
env['ADB'] = ADB
env['ANDROID_ADB_SERVER_PORT'] = PORT

proc = subprocess.Popen(
    [r'D:\Documents\AI learning\Wellphone\.tools\scrcpy-win64-v4.1\scrcpy.exe',
     '-s', SERIAL,
     '--new-display=1080x1920',
     '--start-app=com.android.settings',
     '--display-ime-policy=local',
     '--no-audio', '--stay-awake', '--no-playback',
     '--record=test_stability.mp4', '--record-format=mp4'],
    env=env,
    stdout=open('scrcpy_stab_log.txt', 'w'),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0,
)

time.sleep(8)

if proc.poll() is not None:
    with open('scrcpy_stab_log.txt', 'r') as f:
        print("FAIL:", f.read()[-1000:])
    sys.exit(1)

with open('scrcpy_pid.txt', 'w') as f:
    f.write(str(proc.pid))
print(f"scrcpy PID={proc.pid}")

def adb_shell(cmd):
    r = subprocess.run([ADB, '-P', PORT, '-s', SERIAL, 'shell', cmd],
                       capture_output=True, text=True, timeout=10)
    return r.returncode, r.stdout.strip()

log = adb_shell("dumpsys SurfaceFlinger | grep 'New display' | tail -1")
print(f"Display info: {log[1]}")

results = []
for i in range(60):
    x = 100 + (i * 15) % 880
    y = 200 + (i * 23) % 1500
    rc, out = adb_shell(f"input -d 7 tap {x} {y}")
    ok = (rc == 0)
    results.append(ok)
    if i % 10 == 9:
        rc2, focus = adb_shell("dumpsys window | grep mCurrentFocus")
        settings_ok = "com.android.settings" in focus
        print(f"  step {i+1}/60: ok={ok}, main_focus={focus[:60]}... settings_on_main={settings_ok}")

success_count = sum(results)
print(f"\n=== D1-7/D1-12 结果 ===")
print(f"成功: {success_count}/60, 失败: {60-success_count}/60")

rc, meminfo = adb_shell("dumpsys meminfo com.android.settings | grep -E 'TOTAL|Native Heap|Dalvik Heap'")
print(f"设置 App 内存:\n{meminfo}")

rc, proc_mem = adb_shell(f"cat /proc/{proc.pid}/status 2>/dev/null | grep -E 'VmRSS|VmSize'")
print(f"scrcpy 进程内存: {proc_mem}")

ls_result = subprocess.run(['ls', '-la', 'test_stability.mp4'], capture_output=True, text=True)
print(f"录屏文件: {ls_result.stdout.strip()}")

if proc.poll() is None:
    print("scrcpy 仍在运行: 稳定性确认")
else:
    print(f"scrcpy 已退出: code={proc.returncode}")
