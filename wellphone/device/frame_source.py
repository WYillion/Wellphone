from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod


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
    def __init__(self, scrcpy_bin: str, serial: str | None = None, fps: int = 8):
        self._scrcpy = scrcpy_bin
        self._serial = serial
        self._fps = fps
        self._path: str | None = None
        self._process: subprocess.Popen | None = None
        self._display_id = 0

    def start(self, display_id: int) -> None:
        if self._process is not None:
            return
        if shutil.which("ffmpeg") is None:
            raise FrameSourceError(
                "ffmpeg is required to decode the scrcpy record stream; "
                "install it or fall back to ScreencapSource"
            )
        self._display_id = display_id
        self._path = tempfile.NamedTemporaryFile(
            prefix="wellphone_", suffix=".h264", delete=False
        ).name
        cmd = [self._scrcpy]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += [
            f"--display-id={display_id}",
            "--no-audio",
            "--no-window",
            f"--max-fps={self._fps}",
            "--video-codec=h264",
            f"--record={self._path}",
        ]
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(1.0)

    def capture(self) -> bytes:
        if not self._path:
            raise FrameSourceError("source not started")
        result = subprocess.run(
            [
                "ffmpeg",
                "-sseof",
                "-0.2",
                "-i",
                self._path,
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
            raise FrameSourceError("failed to decode latest frame from scrcpy stream")
        return result.stdout

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
