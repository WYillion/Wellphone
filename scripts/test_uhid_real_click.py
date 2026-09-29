"""验证 UHID 模式 + 真实鼠标事件（SetCursorPos + mouse_event）"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from PIL import Image, ImageChops

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


def real_click(hwnd, win_x, win_y):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    screen_x = rect.left + win_x
    screen_y = rect.top + win_y

    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    time.sleep(0.5)


s = load_settings()
env = s.adb_env()

cmd = [
    s.scrcpy_bin, "-s", s.serial,
    "--new-display=1080x1920/373",
    "--display-ime-policy=local", "--keep-active", "--no-audio",
    "--always-on-top", "--mouse=uhid", "--keyboard=uhid",
    "-b", "8M", "--start-app=com.android.settings",
]
print("启动 scrcpy (uhid):", " ".join(cmd))
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

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
img1 = capture_window(hwnd)
print(f"窗口大小: {img1.size}")
img1.save("workspace/uhid2_before.png")

rect = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(rect))
ww, wh = rect.right - rect.left, rect.bottom - rect.top

target_x, target_y = 499, 620
win_x = int(target_x * ww / 1080)
win_y = int(target_y * wh / 1920)
print(f"点击虚拟屏 ({target_x}, {target_y}) -> 窗口 ({win_x}, {win_y})")

real_click(hwnd, win_x, win_y)
time.sleep(3)

img2 = capture_window(hwnd)
img2.save("workspace/uhid2_after.png")

diff = ImageChops.difference(img1, img2)
bbox = diff.getbbox()
print(f"diff bbox: {bbox}")
if bbox is None:
    print("两张截图相同 - 点击未生效")
else:
    print(f"差异区域: {bbox} - 点击可能生效!")

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
print("done")
