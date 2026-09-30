from __future__ import annotations

import re
from dataclasses import replace

from wellphone.agent.action_space import Action, TAP, DOUBLE_TAP, LONG_PRESS, LAUNCH
from wellphone.agent.model_provider import ModelProvider

_PACKAGE_ALIASES = {
    "微信": "com.tencent.mm",
    "美团": "com.sankuai.meituan",
    "设置": "com.android.settings",
    "QQ": "com.tencent.mobileqq",
    "抖音": "com.ss.android.ugc.aweme",
    "支付宝": "com.eg.android.AlipayGphone",
}

_ELEMENT_RE = re.compile(
    r'<node[^>]*?(?:text="([^"]*)")[^>]*?(?:content-desc="([^"]*)")'
    r'[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
    re.DOTALL,
)
_CLICKABLE_ATTR_RE = re.compile(r'clickable="true"')


def _parse_ui_elements(ui_dump: str) -> list[tuple[str, int, int, int, int]]:
    elements: list[tuple[str, int, int, int, int]] = []
    for m in _ELEMENT_RE.finditer(ui_dump):
        text = (m.group(1) or "").strip()
        desc = (m.group(2) or "").strip()
        label = text or desc
        if not label:
            continue
        x1, y1, x2, y2 = int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
        elements.append((label, x1, y1, x2, y2))
    return elements


def _snap_to_element(
    x: int, y: int, elements: list[tuple[str, int, int, int, int]],
    max_distance: int = 150,
) -> tuple[int, int]:
    best = None
    best_dist = float("inf")
    for label, x1, y1, x2, y2 in elements:
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if x1 <= x <= x2 and y1 <= y <= y2:
            return cx, cy
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = (cx, cy)
    if best and best_dist <= max_distance:
        return best
    return x, y


class VlmAgent:
    def __init__(
        self,
        provider: ModelProvider,
        display_id: int,
        display_width: int = 0,
        display_height: int = 0,
    ):
        self._provider = provider
        self._display_id = display_id
        self._display_width = display_width
        self._display_height = display_height

    def decide(
        self,
        task: str,
        screenshot_png: bytes | None = None,
        ui_dump: str = "",
        history: list[str] | None = None,
        capture_size: tuple[int, int] = (0, 0),
        raw_ui_dump: str = "",
    ) -> Action:
        payload = self._provider.decide(
            task, screenshot_png, ui_dump, list(history or [])
        )
        reasoning = self._provider.extract_reasoning(payload)
        action = self._provider.parse_action(payload, self._display_id)
        action = self._scale_coords(action, capture_size)
        action = self._correct_action(action, reasoning, raw_ui_dump)
        return action

    def _scale_coords(self, action: Action, capture_size: tuple[int, int]) -> Action:
        cw, ch = capture_size
        if not cw or not ch or not self._display_width or not self._display_height:
            return action
        if cw == self._display_width and ch == self._display_height:
            return action
        sx = self._display_width / cw
        sy = self._display_height / ch
        x = int(round(action.x * sx)) if action.x is not None else None
        y = int(round(action.y * sy)) if action.y is not None else None
        x2 = int(round(action.x2 * sx)) if action.x2 is not None else None
        y2 = int(round(action.y2 * sy)) if action.y2 is not None else None
        return replace(action, x=x, y=y, x2=x2, y2=y2)

    def _correct_action(
        self, action: Action, reasoning: str, raw_ui_dump: str
    ) -> Action:
        if action.name == LAUNCH and action.package:
            pkg = action.package.strip()
            if pkg in _PACKAGE_ALIASES:
                return replace(action, package=_PACKAGE_ALIASES[pkg])
        if not raw_ui_dump or action.x is None or action.y is None:
            return action
        if action.name not in (TAP, DOUBLE_TAP, LONG_PRESS):
            return action
        elements = _parse_ui_elements(raw_ui_dump)
        if not elements:
            return action
        dw, dh = self._display_width, self._display_height
        if dw and dh:
            elements = [
                e for e in elements
                if (e[1] + e[3]) // 2 < dw and (e[2] + e[4]) // 2 < dh
            ]
        if not elements:
            return action
        target = _find_target_element(reasoning, elements)
        if target:
            cx, cy = target
            if not dw or not dh or (0 <= cx < dw and 0 <= cy < dh):
                return replace(action, x=cx, y=cy)
        new_x, new_y = _snap_to_element(action.x, action.y, elements)
        if (new_x, new_y) != (action.x, action.y):
            return replace(action, x=new_x, y=new_y)
        return action


def _find_target_element(
    reasoning: str, elements: list[tuple[str, int, int, int, int]]
) -> tuple[int, int] | None:
    if not reasoning:
        return None
    patterns = [
        r'(?:点击|点击一下|选择|tap|click|press)\s*["\u201c]?([^"\u201d，。,\s]{2,20})["\u201d]?',
        r'["\u201c]([^"\u201d]{2,20})["\u201d].*?(?:选项|按钮|项|entry|option|button)',
    ]
    candidates: list[str] = []
    for pattern in patterns:
        for m in re.finditer(pattern, reasoning, re.IGNORECASE):
            candidates.append(m.group(1))
    for candidate in candidates:
        for label, x1, y1, x2, y2 in elements:
            if candidate == label or candidate in label or label in candidate:
                return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None
