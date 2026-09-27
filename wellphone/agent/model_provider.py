from __future__ import annotations

import base64
import json
import re

import requests

from wellphone.agent.action_space import ACTIONS, FINISH, Action


class ModelProviderError(RuntimeError):
    pass


SYSTEM_PROMPT = """You control an Android app running on a dedicated virtual display.
All coordinates are display-local pixels of that virtual display; the user's real main display must never be affected.
Available actions: {actions}.
Rules:
1. Reply with exactly one JSON object and nothing else.
2. JSON shape: {{"name": "<action>", "package": "...", "x": 0, "y": 0, "x2": 0, "y2": 0, "text": "...", "reason": "...", "duration_ms": 300}}.
3. Omit fields the action does not need; always include "reason" for Take_over and Wait.
4. Never enter passwords, payment PINs or verification codes yourself: choose Take_over with a short reason.
5. Prefer tapping visible targets from the UI dump; use Wait after navigation; call Finish when the task is done.
"""


class ModelProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def decide(
        self,
        task: str,
        screenshot_png: bytes | None,
        ui_dump: str,
        history: list[str],
    ) -> dict:
        text_block = f"Task: {task}\n"
        if history:
            text_block += "Recent actions:\n" + "\n".join(history[-6:]) + "\n"
        if ui_dump:
            text_block += "UI dump (display-local):\n" + ui_dump[:6000]
        content: list[dict] = [{"type": "text", "text": text_block}]
        if screenshot_png:
            b64 = base64.b64encode(screenshot_png).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(actions=", ".join(ACTIONS)),
                },
                {"role": "user", "content": content},
            ],
            "max_tokens": 512,
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise ModelProviderError(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ModelProviderError(
                f"model API returned {resp.status_code}: {resp.text[:300]}"
            )
        try:
            content_str = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ModelProviderError(f"unexpected response shape: {resp.text[:300]}") from exc
        return self._extract_json(content_str)

    @staticmethod
    def _extract_json(content: str) -> dict:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ModelProviderError(f"no JSON object in model reply: {content[:200]!r}")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ModelProviderError(f"invalid JSON in model reply: {content[:200]!r}") from exc

    @staticmethod
    def parse_action(payload: dict, display_id: int) -> Action:
        name = payload.get("name", "")
        if name not in ACTIONS:
            raise ModelProviderError(f"unknown action {name!r}")
        return Action(
            name=name,
            display_id=display_id,
            x=payload.get("x"),
            y=payload.get("y"),
            x2=payload.get("x2"),
            y2=payload.get("y2"),
            text=payload.get("text"),
            package=payload.get("package"),
            reason=payload.get("reason"),
            duration_ms=payload.get("duration_ms", 300),
        )


class ScriptedProvider:
    def __init__(self, script: list[dict]):
        self._script = list(script)

    def decide(
        self,
        task: str,
        screenshot_png: bytes | None,
        ui_dump: str,
        history: list[str],
    ) -> dict:
        if self._script:
            return self._script.pop(0)
        return {"name": FINISH_ACTION, "reason": "script exhausted"}

    def parse_action(self, payload: dict, display_id: int) -> Action:
        return ModelProvider.parse_action(payload, display_id)
