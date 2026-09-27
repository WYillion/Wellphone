from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from wellphone.agent.action_space import Action

ALLOW = "allow"
PAUSE = "pause"

SENSITIVE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"支付", r"付款", r"密码", r"验证码", r"删除", r"同意",
        r"协议", r"授权", r"fingerprint", r"password", r"passcode",
        r"pay(ment)?\b", r"checkout", r"verify", r"otp", r"agree",
    )
)


@dataclass(frozen=True)
class GateDecision:
    verdict: str
    rule: str


class TakeOverGate:
    def __init__(
        self,
        model_checker: Callable[[Action, str], bool] | None = None,
    ):
        self._model_checker = model_checker

    def check(self, action: Action, page_text: str = "") -> GateDecision:
        targets = " ".join(
            t for t in (action.reason, action.text, page_text) if t
        )
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(targets):
                return GateDecision(PAUSE, f"rule:{pattern.pattern}")
        if self._model_checker is not None and self._model_checker(action, page_text):
            return GateDecision(PAUSE, "rule:model_checker")
        return GateDecision(ALLOW, "rule:none")
