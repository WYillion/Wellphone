"""调试截图来源：建虚拟屏 + ScrcpyWindowSource 截图 + 打印窗口信息"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.config.settings import load_settings
from wellphone.device.adb_client import AdbClient
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.device.frame_source import ScrcpyWindowSource

user32 = ctypes.windll.user32

s = load_settings()
adb = AdbClient(s)
runner = VirtualDisplayRunner(s, adb)

print("建虚拟屏 + 启动设置 app ...")
did = runner.create(start_app="com.android.settings")
print(f"display_id = {did}")
print(f"scrcpy pid = {runner.process_pid}")

time.sleep(3)

print("\n=== scrcpy 进程的所有可见窗口 ===")
target_pid = runner.process_pid
found = []
def callback(hwnd, _):
    wpid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
    if wpid.value == target_pid:
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        visible = bool(user32.IsWindowVisible(hwnd))
        found.append((hwnd, title, visible, rect.left, rect.top,
                      rect.right - rect.left, rect.bottom - rect.top))
    return True
wndproc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(wndproc(callback), 0)
for f in found:
    print(f"  hwnd={f[0]} title={f[1]!r} visible={f[2]} pos=({f[3]},{f[4]}) size={f[5]}x{f[6]}")

print("\n=== ScrcpyWindowSource 截图 ===")
source = ScrcpyWindowSource(
    pid=runner.process_pid,
    target_width=s.display_width,
    target_height=s.display_height,
)
source.start(did)
png = source.capture()
out = os.path.abspath("workspace/debug_shot.png")
with open(out, "wb") as f:
    f.write(png)
print(f"截图保存: {out} ({len(png)} bytes)")

print("\n=== 虚拟屏上的 app ===")
print(adb.shell(f"dumpsys activity activities | grep -E 'Display #{did}|mResumedActivity' | head -20"))

runner.destroy()
