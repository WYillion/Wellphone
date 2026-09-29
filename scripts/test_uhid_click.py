"""验证 scrcpy --mouse=uhid 模式：启动 scrcpy → PostMessage 发送点击 → 截图验证"""
import ctypes
import io
import os
import subprocess
import sys
import time
from ctypes import wintypes
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from wellphone.config.settings import load_settings

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def find_window_by_pid(pid):
    found = []
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                found.append(hwnd)
        return True
    wndproc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(wndproc(callback), 0)
    return found[0] if found else None


def capture_window(hwnd):
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    cw, ch = rect.right - rect.left, rect.bottom - rect.top
    if cw <= 0 or ch <= 0:
        return None
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, cw, ch)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 0x00000002)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BIH()
    bi.biSize = ctypes.sizeof(bi)
    bi.biWidth = cw
    bi.biHeight = -ch
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(cw * ch * 4)
    gdi32.GetDIBits(mdc, bmp, 0, ch, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (cw, ch), buf.raw, "raw", "BGRA", 0, 1)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return img


def click_window(hwnd, x, y):
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    lparam = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)


s = load_settings()
env = s.adb_env()

cmd = [
    s.scrcpy_bin, "-s", s.serial,
    "--new-display=1080x1920/373",
    "--display-ime-policy=local", "--keep-active", "--no-audio",
    "--always-on-top", "--mouse=uhid", "--keyboard=uhid",
    "-b", "8M", "--start-app=com.android.settings",
]
print("启动 scrcpy (uhid mode):", " ".join(cmd))
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

print("等待窗口...")
hwnd = None
for _ in range(20):
    time.sleep(1)
    hwnd = find_window_by_pid(proc.pid)
    if hwnd:
        break
if not hwnd:
    print("窗口未找到!")
    proc.terminate()
    sys.exit(1)

time.sleep(3)
img = capture_window(hwnd)
print(f"窗口大小: {img.size}")
img.save("workspace/uhid_before.png")
print(f"截图保存: workspace/uhid_before.png ({os.path.getsize('workspace/uhid_before.png')} bytes)")

rect = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(rect))
ww, wh = rect.right - rect.left, rect.bottom - rect.top

target_x, target_y = 499, 620
win_x = int(target_x * ww / 1080)
win_y = int(target_y * wh / 1920)
print(f"点击虚拟屏 ({target_x}, {target_y}) -> 窗口 ({win_x}, {win_y})")

click_window(hwnd, win_x, win_y)
time.sleep(3)

img2 = capture_window(hwnd)
img2.save("workspace/uhid_after.png")
print(f"点击后截图: workspace/uhid_after.png ({os.path.getsize('workspace/uhid_after.png')} bytes)")

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
print("done")
