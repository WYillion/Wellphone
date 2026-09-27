from __future__ import annotations

import subprocess
import time

from wellphone.config.settings import Settings
from wellphone.device.adb_client import AdbClient

DRY_RUN_DISPLAY_ID = 21


class VirtualDisplayError(RuntimeError):
    pass


class VirtualDisplayRunner:
    def __init__(self, settings: Settings, adb: AdbClient):
        self._settings = settings
        self._adb = adb
        self._process: subprocess.Popen | None = None

    def _scrcpy_cmd(self, size: str, start_app: str | None) -> list[str]:
        cmd = [self._settings.scrcpy_bin]
        if self._settings.serial:
            cmd += ["-s", self._settings.serial]
        cmd += [
            f"--new-display={size}",
            "--display-ime-policy=local",
            "--keep-active",
            "--no-audio",
            "-b",
            "8M",
        ]
        if start_app:
            cmd.append(f"--start-app={start_app}")
        return cmd

    def create(self, start_app: str | None = None, wait_s: float = 15.0) -> int:
        size = (
            f"{self._settings.display_width}x{self._settings.display_height}"
            f"/{self._settings.display_dpi}"
        )
        cmd = self._scrcpy_cmd(size, start_app)
        if self._settings.dry_run:
            print(f"[dry-run] {' '.join(cmd)}")
            return DRY_RUN_DISPLAY_ID

        before = set(self._adb.list_displays())
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        deadline = time.time() + wait_s
        while time.time() < deadline:
            if self._process.poll() is not None:
                raise VirtualDisplayError(
                    f"scrcpy exited early with code {self._process.returncode}"
                )
            new_ids = set(self._adb.list_displays()) - before
            if new_ids:
                return new_ids.pop()
            time.sleep(0.5)
        self.destroy()
        raise VirtualDisplayError(
            f"no new virtual display appeared within {wait_s}s"
        )

    def destroy(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def start_app(self, package: str, display_id: int) -> str:
        activity = self._adb.resolve_launch_activity(package)
        return self._adb.shell(
            f"am start --display {display_id} -f 0x10008000 -n {activity}"
        )

    def enable_overlay_display(self, size: str = "1920x1080/200") -> str:
        return self._adb.shell(
            f"settings put global overlay_display_devices '{size}'"
        )

    def disable_overlay_display(self) -> str:
        return self._adb.shell("settings put global overlay_display_devices none")
