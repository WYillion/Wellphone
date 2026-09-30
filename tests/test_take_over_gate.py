from __future__ import annotations

import pytest

from wellphone.agent.action_space import TAP, TYPE, Action
from wellphone.guard.take_over_gate import ALLOW, PAUSE, TakeOverGate


def _action(name: str, **kw) -> Action:
    return Action(name=name, display_id=21, **kw)


def test_rule_blocks_sensitive_text() -> None:
    gate = TakeOverGate()
    decision = gate.check(_action(TYPE, text="我的支付密码是123"))
    assert decision.verdict == PAUSE
    assert decision.rule.startswith("rule:")


def test_rule_blocks_sensitive_page_text() -> None:
    gate = TakeOverGate()
    decision = gate.check(_action(TYPE, text="123456"), page_text="请输入验证码")
    assert decision.verdict == PAUSE


def test_rule_allows_normal_action() -> None:
    gate = TakeOverGate()
    decision = gate.check(_action(TAP, x=100, y=200), page_text="聊天列表")
    assert decision.verdict == ALLOW


def test_model_checker_can_only_harden() -> None:
    gate = TakeOverGate(model_checker=lambda action, page: True)
    decision = gate.check(_action(TAP, x=1, y=2))
    assert decision.verdict == PAUSE
    assert decision.rule == "rule:model_checker"


def test_model_checker_cannot_override_rule() -> None:
    gate = TakeOverGate(model_checker=lambda action, page: False)
    decision = gate.check(_action(TYPE, text="同意本协议"))
    assert decision.verdict == PAUSE


def test_model_checker_exception_does_not_crash() -> None:
    def broken(action, page):
        raise RuntimeError("model down")

    gate = TakeOverGate(model_checker=broken)
    with pytest.raises(RuntimeError):
        gate.check(_action(TAP, x=1, y=2))
