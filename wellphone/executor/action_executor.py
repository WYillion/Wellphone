from __future__ import annotations

import time

from wellphone.agent.action_space import (
    BACK,
    DOUBLE_TAP,
    FINISH,
    HOME,
    LAUNCH,
    LONG_PRESS,
    SWIPE,
    TAP,
    TAKE_OVER,
    TYPE,
    WAIT,
    Action,
)
from wellphone.device.adb_client import AdbClient
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.executor.input_channel import InputChannel


class TakeOverRequested(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ActionExecutor:
    def __init__(
        self,
        adb: AdbClient,
        runner: VirtualDisplayRunner,
        input_channel: InputChannel,
    ):
        self._adb = adb
        self._runner = runner
        self._input = input_channel

    def execute(self, action: Action) -> str:
        handler = {
            LAUNCH: self._launch,
            TAP: self._tap,
            TYPE: self._type,
            SWIPE: self._swipe,
            BACK: self._back,
            HOME: self._home,
            LONG_PRESS: self._long_press,
            DOUBLE_TAP: self._double_tap,
            WAIT: self._wait,
            TAKE_OVER: self._take_over,
            FINISH: self._finish,
        }[action.name]
        return handler(action)

    def _launch(self, action: Action) -> str:
        return self._runner.start_app(action.package or "", action.display_id)

    def _tap(self, action: Action) -> str:
        return self._input.tap(action.x or 0, action.y or 0, action.display_id)

    def _type(self, action: Action) -> str:
        return self._input.send_text(action.text or "", action.display_id)

    def _swipe(self, action: Action) -> str:
        return self._input.swipe(
            action.x or 0,
            action.y or 0,
            action.x2 or action.x or 0,
            action.y2 or action.y or 0,
            action.duration_ms,
            action.display_id,
        )

    def _back(self, action: Action) -> str:
        return self._input.back(action.display_id)

    def _home(self, action: Action) -> str:
        return self._input.home(action.display_id)

    def _long_press(self, action: Action) -> str:
        x, y = action.x or 0, action.y or 0
        return self._input.swipe(x, y, x, y, 800, action.display_id)

    def _double_tap(self, action: Action) -> str:
        x, y = action.x or 0, action.y or 0
        first = self._input.tap(x, y, action.display_id)
        time.sleep(0.1)
        second = self._input.tap(x, y, action.display_id)
        return first + second

    def _wait(self, action: Action) -> str:
        time.sleep(min(action.duration_ms, 5000) / 1000.0)
        return "waited"

    def _take_over(self, action: Action) -> str:
        raise TakeOverRequested(action.reason or "agent requested take over")

    def _finish(self, action: Action) -> str:
        return "finish"
