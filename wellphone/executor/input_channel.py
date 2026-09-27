from __future__ import annotations

from wellphone.device.adb_client import AdbClient

KEYCODE_BACK = 4
KEYCODE_HOME = 3
KEYCODE_ENTER = 66
KEYCODE_SEARCH = 84


class InputChannel:
    def __init__(self, adb: AdbClient):
        self._adb = adb

    def tap(self, x: int, y: int, display_id: int) -> str:
        return self._adb.tap(x, y, display_id)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        display_id: int | None = None,
    ) -> str:
        return self._adb.swipe(x1, y1, x2, y2, duration_ms, display_id)

    def back(self, display_id: int) -> str:
        return self._adb.keyevent(KEYCODE_BACK, display_id)

    def home(self, display_id: int) -> str:
        return self._adb.keyevent(KEYCODE_HOME, display_id)

    def keyevent(self, keycode: int, display_id: int) -> str:
        return self._adb.keyevent(keycode, display_id)

    def send_text_ascii(self, text: str, display_id: int) -> str:
        return self._adb.input_text(text, display_id)

    def send_text_adb_keyboard(self, text: str, display_id: int) -> str:
        self._adb._assert_display(display_id)
        return self._adb.shell(
            f"am broadcast -a ADB_INPUT_TEXT --es msg '{text}'"
        )

    def send_text(self, text: str, display_id: int) -> str:
        if text.isascii():
            return self.send_text_ascii(text, display_id)
        return self.send_text_adb_keyboard(text, display_id)
