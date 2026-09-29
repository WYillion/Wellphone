from __future__ import annotations

import base64
import json
import os
import re

import requests

from wellphone.agent.action_space import ACTIONS, FINISH, Action


class ModelProviderError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are operating an Android app on a dedicated virtual display.
All coordinates are display-local pixels of that virtual display.
The user's real main display must never be affected.
Never enter passwords, payment PINs or verification codes: use Take_over with a short reason.
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
                    "content": SYSTEM_PROMPT,
                },
                {"role": "user", "content": content},
            ],
            "max_tokens": 3000,
            "temperature": 0.0,
            "top_p": 0.85,
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
        if os.environ.get("WELLPHONE_DEBUG_API"):
            print(f"[debug] API response:\n{content_str[:1000]}")
        return self._parse_response(content_str)

    @staticmethod
    def _parse_response(content: str) -> dict:
        finish_match = re.search(r'finish\s*\(\s*message\s*=\s*"(.*?)"\s*\)', content, re.DOTALL)
        if finish_match:
            return {"name": FINISH, "reason": finish_match.group(1)}

        do_match = re.search(r'do\s*\(\s*action\s*=\s*(\w+)\s*\((.*?)\)\s*\)', content, re.DOTALL)
        if do_match:
            action_name = do_match.group(1)
            params_str = do_match.group(2)
            params = ModelProvider._parse_params(params_str)
            params["name"] = action_name
            return params

        do_str_match = re.search(
            r'do\s*\(\s*action\s*=\s*"(\w+)"\s*,?\s*(.*?)\s*\)', content, re.DOTALL
        )
        if do_str_match:
            action_name = do_str_match.group(1)
            params_str = do_str_match.group(2)
            params = ModelProvider._parse_params(params_str)
            params["name"] = action_name
            if "message" in params and "reason" not in params:
                params["reason"] = params.pop("message")
            return params

        action_names = "|".join(ACTIONS)
        action_match = re.search(
            rf'\b({action_names})\s*\((.*?)\)', content, re.DOTALL
        )
        if action_match:
            action_name = action_match.group(1)
            params_str = action_match.group(2)
            params = ModelProvider._parse_params(params_str)
            if not params and params_str.strip():
                parts = [p.strip() for p in params_str.split(",") if p.strip()]
                if action_name in ("Tap", "DoubleTap", "LongPress") and len(parts) >= 2:
                    params = {"x": int(parts[0]), "y": int(parts[1])}
                elif action_name == "Swipe" and len(parts) >= 4:
                    params = {
                        "x": int(parts[0]), "y": int(parts[1]),
                        "x2": int(parts[2]), "y2": int(parts[3]),
                    }
            params["name"] = action_name
            if "message" in params and "reason" not in params:
                params["reason"] = params.pop("message")
            return params

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ModelProviderError(f"cannot parse model reply: {content[-300:]!r}")

    @staticmethod
    def _parse_params(params_str: str) -> dict:
        result = {}
        pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|(\d+))'
        for match in re.finditer(pattern, params_str):
            key = match.group(1)
            if match.group(2) is not None:
                result[key] = match.group(2)
            elif match.group(3) is not None:
                result[key] = int(match.group(3))
        return result

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
        return {"name": FINISH, "reason": "script exhausted"}

    def parse_action(self, payload: dict, display_id: int) -> Action:
        return ModelProvider.parse_action(payload, display_id)
