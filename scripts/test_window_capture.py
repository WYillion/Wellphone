"""验证 scrcpy 窗口截图方案：启动 scrcpy 开窗口 → ctypes 找窗口 → PIL 截图"""
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


def find_windows():
    results = []
    def callback(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if user32.IsWindowVisible(hwnd):
                results.append((hwnd, title))
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return results


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

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]
    bi = BITMAPINFOHEADER()
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


s = load_settings()
env = s.adb_env()

cmd = [
    s.scrcpy_bin, "-s", s.serial,
    "--new-display=1080x1920/373",
    "--display-ime-policy=local", "--keep-active", "--no-audio",
    "--always-on-top", "-b", "8M", "--max-fps=8",
    "--start-app=com.android.settings",
]
print("启动 scrcpy:", " ".join(cmd))
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

print("等待窗口出现...")
hwnd = None
for _ in range(20):
    time.sleep(1)
    for h, title in find_windows():
        if "scrcpy" in title.lower() or "24129" in title or "settings" in title.lower():
            hwnd = h
            print(f"找到窗口: hwnd={h}, title={title!r}")
            break
    if hwnd:
        break

if not hwnd:
    print("未找到 scrcpy 窗口！所有可见窗口:")
    for h, title in find_windows():
        print(f"  {h}: {title!r}")
    proc.terminate()
    sys.exit(1)

print("\n截取窗口画面...")
for i in range(3):
    time.sleep(1)
    img = capture_window(hwnd)
    if img:
        out = f"workspace/window_shot_{i}.png"
        img.save(out)
        print(f"  shot {i}: {img.size}, saved {out} ({os.path.getsize(out)} bytes)")
    else:
        print(f"  shot {i}: failed")

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
print("done")
