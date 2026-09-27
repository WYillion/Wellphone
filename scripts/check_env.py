from __future__ import annotations

import importlib
import shutil
import subprocess
import sys

CHECKS: list[tuple[str, object]] = [
    ("python", lambda: f"{sys.version_info.major}.{sys.version_info.minor}"),
    ("adb", lambda: shutil.which("adb")),
    ("scrcpy", lambda: shutil.which("scrcpy")),
    ("ffmpeg", lambda: shutil.which("ffmpeg")),
]

MODULES = ("requests", "PIL", "langgraph")


def _adb_devices(adb_path: str) -> str:
    try:
        out = subprocess.run(
            [adb_path, "devices"], capture_output=True, text=True, timeout=10, check=False
        )
        return out.stdout.strip().replace("\n", " | ")
    except Exception as exc:
        return f"error: {exc}"


def main() -> int:
    ok = True
    for name, probe in CHECKS:
        value = probe()
        status = "OK" if value else "MISSING"
        if not value and name in ("adb", "scrcpy"):
            ok = False
        print(f"  [{status:>7}] {name}: {value or '-'}")

    adb_path = shutil.which("adb")
    if adb_path:
        print(f"  devices: {_adb_devices(adb_path)}")

    for module in MODULES:
        try:
            importlib.import_module(module)
            print(f"  [      OK] module {module}")
        except ImportError:
            print(f"  [ MISSING] module {module}")
            ok = False

    print()
    if ok:
        print("environment ready; next: connect a device and run D1 checks")
    else:
        print(
            "incomplete environment: install adb/scrcpy (and Python deps via "
            "`pip install -r requirements.txt`), then re-run this script"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
