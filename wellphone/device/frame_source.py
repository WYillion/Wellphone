from __future__ import annotations

import ctypes
import io
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from ctypes import wintypes

from PIL import Image


class FrameSourceError(RuntimeError):
    pass


class FrameSource(ABC):
    @abstractmethod
    def start(self, display_id: int) -> None: ...

    @abstractmethod
    def capture(self) -> bytes: ...

    @abstractmethod
    def stop(self) -> None: ...


class ScreencapSource(FrameSource):
    def __init__(self, adb):
        self._adb = adb
        self._display_id = 0

    def start(self, display_id: int) -> None:
        self._display_id = display_id

    def capture(self) -> bytes:
        try:
            return self._adb.exec_out([f"screencap -d {self._display_id} -p"])
        except Exception as exc:
            raise FrameSourceError(
                f"screencap -d {self._display_id} failed "
                f"(known limitation on some Android versions): {exc}"
            ) from exc

    def stop(self) -> None:
        return None


class ScrcpyRecordSource(FrameSource):
    def __init__(
        self,
        scrcpy_bin: str,
        serial: str | None = None,
        fps: int = 8,
        ffmpeg_bin: str = "ffmpeg",
        env: dict | None = None,
    ):
        self._scrcpy = scrcpy_bin
        self._serial = serial
        self._fps = fps
        self._ffmpeg = ffmpeg_bin
        self._env = env
        self._path: str | None = None
        self._process: subprocess.Popen | None = None
        self._display_id = 0

    def start(self, display_id: int) -> None:
        if self._process is not None:
            return
        if shutil.which(self._ffmpeg) is None and not os.path.isfile(self._ffmpeg):
            raise FrameSourceError(
                "ffmpeg is required to decode the scrcpy record stream; "
                "install it or fall back to ScreencapSource"
            )
        self._display_id = display_id
        self._path = tempfile.NamedTemporaryFile(
            prefix="wellphone_", suffix=".mkv", delete=False
        ).name
        cmd = [self._scrcpy]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += [
            f"--display-id={display_id}",
            "--no-audio",
            "--no-playback",
            f"--max-fps={self._fps}",
            "--video-codec=h264",
            "--record-format=mkv",
            f"--record={self._path}",
        ]
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self._env
        )
        time.sleep(1.0)

    def capture(self) -> bytes:
        if not self._path:
            raise FrameSourceError("source not started")
        return _decode_last_frame(self._path, self._ffmpeg)

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None


def _decode_last_frame(path: str, ffmpeg_bin: str) -> bytes:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise FrameSourceError(f"record file not ready: {path}")
    result = subprocess.run(
        [
            ffmpeg_bin,
            "-sseof",
            "-0.5",
            "-i",
            path,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
        timeout=10.0,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        detail = result.stderr.decode(errors="replace")[-600:]
        size = os.path.getsize(path) if os.path.exists(path) else -1
        raise FrameSourceError(
            f"failed to decode latest frame from record file "
            f"(rc={result.returncode}, record_size={size}): {detail}"
        )
    return result.stdout


class MkvFileSource(FrameSource):
    def __init__(self, path: str, ffmpeg_bin: str = "ffmpeg"):
        self._path = path
        self._ffmpeg = ffmpeg_bin
        self._display_id = 0

    def start(self, display_id: int) -> None:
        self._display_id = display_id

    def capture(self) -> bytes:
        return _decode_last_frame(self._path, self._ffmpeg)

    def stop(self) -> None:
        return None


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _print_window(hwnd: int) -> Image.Image | None:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

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

    bi = _BitmapInfoHeader()
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


class ScrcpyWindowSource(FrameSource):
    """通过截取 scrcpy 本地窗口获取虚拟屏画面。

    scrcpy 以 --always-on-top 开窗显示虚拟屏内容，
    本类用 Win32 PrintWindow API 截取窗口画面（即使被遮挡也能截到）。
    """

    def __init__(self, pid: int | None = None, title_hint: str = "",
                 target_width: int = 0, target_height: int = 0):
        self._pid = pid
        self._title_hint = title_hint
        self._target_width = target_width
        self._target_height = target_height
        self._hwnd: int | None = None
        self._display_id = 0
        self._capture_width = 0
        self._capture_height = 0

    def _find_window(self) -> int | None:
        user32 = ctypes.windll.user32
        found: list[int] = []

        def callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            if self._pid:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value != self._pid:
                    return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if self._title_hint and self._title_hint not in title:
                return True
            found.append(hwnd)
            return True

        wndproc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(wndproc(callback), 0)
        return found[0] if found else None

    def start(self, display_id: int) -> None:
        self._display_id = display_id
        for _ in range(20):
            self._hwnd = self._find_window()
            if self._hwnd:
                time.sleep(3.0)
                return
            time.sleep(0.5)
        raise FrameSourceError("scrcpy window not found")

    def capture(self) -> bytes:
        if not self._hwnd:
            raise FrameSourceError("source not started")
        img = _print_window(self._hwnd)
        if img is None:
            raise FrameSourceError("failed to capture scrcpy window")
        if self._target_width and self._target_height:
            img = img.resize(
                (self._target_width, self._target_height), Image.LANCZOS
            )
        self._capture_width = img.width
        self._capture_height = img.height
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()

    @property
    def capture_size(self) -> tuple[int, int]:
        return (self._capture_width, self._capture_height)

    def stop(self) -> None:
        return None
