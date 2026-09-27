from __future__ import annotations

import time
from dataclasses import dataclass, field

from wellphone.agent.action_space import FINISH
from wellphone.device.frame_source import FrameSource, FrameSourceError
from wellphone.executor.action_executor import ActionExecutor, TakeOverRequested
from wellphone.guard.take_over_gate import PAUSE, TakeOverGate


@dataclass
class MissionResult:
    status: str
    steps: int
    log: list[str] = field(default_factory=list)


class MissionPlan:
    def __init__(
        self,
        frame_source: FrameSource,
        agent,
        gate: TakeOverGate,
        executor: ActionExecutor,
        max_steps: int = 40,
        step_interval_s: float = 1.5,
        ui_dump_provider=None,
    ):
        self._frame_source = frame_source
        self._agent = agent
        self._gate = gate
        self._executor = executor
        self._max_steps = max_steps
        self._step_interval_s = step_interval_s
        self._ui_dump_provider = ui_dump_provider

    def _observe(self) -> tuple[bytes | None, str]:
        screenshot: bytes | None = None
        try:
            screenshot = self._frame_source.capture()
        except FrameSourceError:
            screenshot = None
        ui_dump = ""
        if self._ui_dump_provider is not None:
            try:
                ui_dump = self._ui_dump_provider()
            except Exception:
                ui_dump = ""
        return screenshot, ui_dump

    def run(self, task: str) -> MissionResult:
        log: list[str] = []
        for step in range(1, self._max_steps + 1):
            screenshot, ui_dump = self._observe()
            action = self._agent.decide(task, screenshot, ui_dump, log)
            decision = self._gate.check(action, ui_dump)
            if decision.verdict == PAUSE:
                log.append(
                    f"[gate] step {step}: {action.name} blocked by {decision.rule}, "
                    "handing over to user"
                )
                return MissionResult("take_over", step, log)
            try:
                outcome = self._executor.execute(action)
            except TakeOverRequested as exc:
                log.append(f"[take_over] step {step}: {exc.reason}")
                return MissionResult("take_over", step, log)
            log.append(f"[step {step}] {action.name} -> {outcome[:120]}")
            if action.name == FINISH:
                return MissionResult("finish", step, log)
            time.sleep(self._step_interval_s)
        return MissionResult("max_steps_reached", self._max_steps, log)
