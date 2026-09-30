from __future__ import annotations

import os
import re
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


def _action_hint(action) -> str:
    parts = []
    if action.x is not None and action.y is not None:
        parts.append(f"at ({action.x}, {action.y})")
    if action.text:
        parts.append(f"text={action.text!r}")
    if action.package:
        parts.append(f"package={action.package}")
    return (" " + " ".join(parts)) if parts else ""


_VISIBLE_TEXT_RE = re.compile(
    r'(?:text|content-desc)="([^"]+)"'
)

_ELEMENT_RE = re.compile(
    r'<node[^>]*?(?:text="([^"]*)")[^>]*?(?:content-desc="([^"]*)")'
    r'[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
    re.DOTALL,
)


def _extract_visible_text(ui_dump: str) -> str:
    labels = _VISIBLE_TEXT_RE.findall(ui_dump)
    return " ".join(l for l in labels if l)


def _simplify_ui_dump(ui_dump: str) -> str:
    lines: list[str] = []
    for m in _ELEMENT_RE.finditer(ui_dump):
        text = (m.group(1) or "").strip()
        desc = (m.group(2) or "").strip()
        x1, y1, x2, y2 = int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
        label = text or desc
        if not label:
            continue
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        lines.append(f'  "{label}" center=({cx},{cy})')
    return "\n".join(lines)


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

    def _observe(self) -> tuple[bytes | None, str, tuple[int, int]]:
        screenshot: bytes | None = None
        capture_size = (0, 0)
        try:
            screenshot = self._frame_source.capture()
            capture_size = getattr(self._frame_source, "capture_size", (0, 0))
        except FrameSourceError:
            screenshot = None
        ui_dump = ""
        if self._ui_dump_provider is not None:
            try:
                ui_dump = self._ui_dump_provider()
            except Exception:
                ui_dump = ""
        return screenshot, ui_dump, capture_size

    def run(self, task: str) -> MissionResult:
        log: list[str] = []
        save_dir = os.environ.get("WELLPHONE_SAVE_FRAMES")
        for step in range(1, self._max_steps + 1):
            screenshot, ui_dump, capture_size = self._observe()
            if save_dir and screenshot:
                os.makedirs(save_dir, exist_ok=True)
                path = os.path.join(save_dir, f"frame_step_{step}.png")
                with open(path, "wb") as f:
                    f.write(screenshot)
            action = self._agent.decide(
                task, screenshot,
                _simplify_ui_dump(ui_dump) if ui_dump else "",
                log, capture_size=capture_size,
                raw_ui_dump=ui_dump,
            )
            gate_text = _extract_visible_text(ui_dump) if ui_dump else ""
            decision = self._gate.check(action, gate_text)
            if decision.verdict == PAUSE:
                log.append(
                    f"[gate] step {step}: {action.name} blocked by {decision.rule}, "
                    "handing over to user"
                )
                return MissionResult("take_over", step, log)
            try:
                self._executor.execute(action)
            except TakeOverRequested as exc:
                log.append(f"[take_over] step {step}: {exc.reason}")
                return MissionResult("take_over", step, log)
            log.append(f"step {step}: {action.name}{_action_hint(action)}")
            if action.name == FINISH:
                return MissionResult("finish", step, log)
            time.sleep(self._step_interval_s)
        return MissionResult("max_steps_reached", self._max_steps, log)
