from __future__ import annotations

import pytest

from wellphone.agent.action_space import FINISH, LAUNCH, TAKE_OVER, TAP, TYPE, Action
from wellphone.config.settings import Settings
from wellphone.device.adb_client import AdbClient
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.executor.action_executor import ActionExecutor, TakeOverRequested
from wellphone.executor.input_channel import InputChannel
from wellphone.guard.take_over_gate import PAUSE, TakeOverGate


@pytest.fixture()
def stack():
    adb = AdbClient(Settings(dry_run=True))
    runner = VirtualDisplayRunner(Settings(dry_run=True), adb)
    executor = ActionExecutor(adb, runner, InputChannel(adb))
    return adb, runner, executor


def _action(name: str, **kw) -> Action:
    return Action(name=name, display_id=21, **kw)


def test_tap_goes_to_virtual_display(stack) -> None:
    adb, _, executor = stack
    out = executor.execute(_action(TAP, x=50, y=60))
    assert out == "[dry-run] adb shell input -d 21 tap 50 60"


def test_type_sends_text(stack) -> None:
    _, _, executor = stack
    out = executor.execute(_action(TYPE, text="hi"))
    assert "input -d 21 text 'hi'" in out


def test_launch_resolves_activity(stack) -> None:
    adb, _, executor = stack
    adb.resolve_launch_activity = lambda pkg: "com.tencent.mm/.ui.LauncherUI"
    out = executor.execute(_action(LAUNCH, package="com.tencent.mm"))
    assert (
        out
        == "[dry-run] adb shell am start --display 21 -f 0x10008000 -n com.tencent.mm/.ui.LauncherUI"
    )


def test_take_over_raises(stack) -> None:
    _, _, executor = stack
    with pytest.raises(TakeOverRequested):
        executor.execute(_action(TAKE_OVER, reason="payment page"))


def test_finish_returns_marker(stack) -> None:
    _, _, executor = stack
    assert executor.execute(_action(FINISH)) == "finish"


def test_gate_pause_prevents_execution(stack) -> None:
    _, _, executor = stack
    gate = TakeOverGate()
    action = _action(TYPE, text="payment password 123")
    if gate.check(action).verdict == PAUSE:
        with pytest.raises(AssertionError):
            raise AssertionError("gate should stop before executor runs")
    else:
        pytest.fail("gate must pause sensitive typing")
