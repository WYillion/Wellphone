from __future__ import annotations

import pytest

from wellphone.config.settings import Settings
from wellphone.device.adb_client import AdbClient, DisplayIdError


def _client(dry_run: bool = True) -> AdbClient:
    return AdbClient(Settings(dry_run=dry_run))


def test_dry_run_tap_targets_virtual_display() -> None:
    out = _client().tap(120, 340, 21)
    assert out == "[dry-run] adb -P 5037 shell input -d 21 tap 120 340"


def test_dry_run_swipe_includes_duration() -> None:
    out = _client().swipe(1, 2, 3, 4, 500, display_id=9)
    assert out == "[dry-run] adb -P 5037 shell input -d 9 swipe 1 2 3 4 500"


def test_refuses_main_display_tap() -> None:
    with pytest.raises(DisplayIdError):
        _client().tap(10, 10, 0)


def test_refuses_missing_display_id() -> None:
    with pytest.raises(DisplayIdError):
        _client().swipe(1, 2, 3, 4, display_id=None)


def test_refuses_negative_display_id() -> None:
    with pytest.raises(DisplayIdError):
        _client().keyevent(4, -1)


def test_dry_run_ascii_text() -> None:
    out = _client().input_text("hello", 21)
    assert out == "[dry-run] adb -P 5037 shell input -d 21 text 'hello'"


def test_serial_is_injected() -> None:
    client = AdbClient(Settings(dry_run=True, serial="ABC123"))
    out = client.tap(1, 1, 21)
    assert out.startswith("[dry-run] adb -P 5037 -s ABC123 shell")


def test_list_displays_parses_dumpsys() -> None:
    client = _client()
    fake = (
        "Display Devices: size=3\n"
        "  Display 0 (state=ON)\n"
        "Display 3 name=\"scrcpy\" ...\n"
        "  mDisplayId=4\n"
        "Display 21 ...\n"
    )
    client.shell = lambda cmd, timeout=30.0: fake
    assert client.list_displays() == [0, 3, 21]
