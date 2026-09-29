from __future__ import annotations

import re
import subprocess

from wellphone.config.settings import Settings


class AdbError(RuntimeError):
    pass


class DisplayIdError(AdbError):
    pass


class AdbClient:
    def __init__(self, settings: Settings):
        self._adb = settings.adb_bin
        self._port = settings.adb_port
        self._serial = settings.serial
        self._dry_run = settings.dry_run

    def _base_cmd(self) -> list[str]:
        cmd = [self._adb, "-P", str(self._port)]
        if self._serial:
            cmd += ["-s", self._serial]
        return cmd

    def _run(self, args: list[str], timeout: float = 30.0) -> str:
        cmd = self._base_cmd() + args
        if self._dry_run:
            return f"[dry-run] {' '.join(cmd)}"
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except FileNotFoundError as exc:
            raise AdbError(f"adb executable not found: {self._adb!r}") from exc
        if result.returncode != 0:
            raise AdbError(f"`{' '.join(args)}` failed: {result.stderr.strip()}")
        return result.stdout

    def shell(self, command: str, timeout: float = 30.0) -> str:
        return self._run(["shell", command], timeout=timeout)

    def exec_out(self, args: list[str], timeout: float = 30.0) -> bytes:
        cmd = self._base_cmd() + args
        if self._dry_run:
            return f"[dry-run] {' '.join(cmd)}".encode()
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout, check=False
        )
        if result.returncode != 0:
            raise AdbError(f"`{' '.join(args)}` failed: {result.stderr.decode(errors='replace')}")
        return result.stdout

    @staticmethod
    def _assert_display(display_id: int) -> None:
        if not isinstance(display_id, int) or display_id <= 0:
            raise DisplayIdError(
                f"refuse to touch display {display_id!r}: "
                "agent actions must target a virtual display with id > 0"
            )

    def tap(self, x: int, y: int, display_id: int) -> str:
        self._assert_display(display_id)
        return self.shell(f"input -d {display_id} tap {x} {y}")

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        display_id: int | None = None,
    ) -> str:
        self._assert_display(display_id)
        return self.shell(
            f"input -d {display_id} swipe {x1} {y1} {x2} {y2} {duration_ms}"
        )

    def keyevent(self, keycode: int, display_id: int) -> str:
        self._assert_display(display_id)
        return self.shell(f"input -d {display_id} keyevent {keycode}")

    def input_text(self, text: str, display_id: int) -> str:
        self._assert_display(display_id)
        safe = text.replace("'", "")
        return self.shell(f"input -d {display_id} text '{safe}'")

    def list_displays(self) -> list[int]:
        out = self.shell("dumpsys display")
        ids: set[int] = set()
        pattern = re.compile(r"^Display (\d+)\b")
        for line in out.splitlines():
            match = pattern.match(line.strip())
            if match:
                ids.add(int(match.group(1)))
        return sorted(ids)

    def resolve_launch_activity(self, package: str) -> str:
        out = self.shell(f"cmd package resolve-activity --brief {package}")
        for line in out.splitlines():
            line = line.strip()
            if "/" in line and not line.startswith(("priority", "time", "package")):
                return line
        raise AdbError(f"cannot resolve launch activity for {package!r}")

    def current_focus(self) -> str:
        out = self.shell("dumpsys window | grep mCurrentFocus")
        return out.strip()
