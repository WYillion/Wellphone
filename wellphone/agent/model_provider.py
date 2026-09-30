from __future__ import annotations

import base64
import json
import os
import re

import requests

from wellphone.agent.action_space import ACTIONS, FINISH, Action


class ModelProviderError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are an Android GUI agent operating an app on a dedicated virtual display.
All coordinates are display-local pixels of that virtual display (origin top-left).
The user's real main display must never be affected.
Never enter passwords, payment PINs or verification codes: use a Take_over action.

Reply with a short reasoning (2-3 sentences max), then END your reply with exactly ONE action line in this format:
  do(action="Tap", element=[x, y])
  do(action="Swipe", start=[x1, y1], end=[x2, y2])
  do(action="Type", text="...")
  do(action="Launch", package="...")
  do(action="Back")  |  do(action="Home")  |  do(action="Wait")
  do(action="Take_over", message="...")
  finish(message="...")

Rules:
- The action line MUST be the last line of your reply.
- Output only ONE action per reply.
- Do not echo, restate or invent previous steps.
- Tap targets must be pixel coordinates inside the screenshot you were given.
- If a UI dump is provided, prefer the exact element bounds from the UI dump
  over visual estimation from the screenshot. The UI dump bounds are in the
  format [x1,y1][x2,y2]; use the center ((x1+x2)/2, (y1+y2)/2) as the tap target.
- For Launch, use the Android package name (e.g. com.tencent.mm for 微信,
  com.sankuai.meituan for 美团, com.android.settings for 设置).
- The app may already be running on this display; if you see its UI, do not
  re-launch it — proceed with the task directly.
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
            text_block += (
                f"Actions already executed ({len(history)}, most recent last) "
                "- for context only, do not copy this format or repeat these:\n"
            )
            text_block += "\n".join(f"  {h}" for h in history[-6:]) + "\n"
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
            "max_tokens": 4000,
            "temperature": 0.1,
            "top_p": 0.85,
        }
        last_error: ModelProviderError | None = None
        for attempt in range(2):
            content_str = self._request(payload)
            if os.environ.get("WELLPHONE_DEBUG_API"):
                print(f"[debug] API response (attempt {attempt + 1}):\n{content_str[:1000]}")
            try:
                result = self._parse_response(content_str)
                result["_reasoning"] = content_str
                return result
            except ModelProviderError as exc:
                last_error = exc
        raise ModelProviderError(f"unparseable reply after 2 attempts: {last_error}")

    def _request(self, payload: dict) -> str:
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
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ModelProviderError(f"unexpected response shape: {resp.text[:300]}") from exc

    @staticmethod
    def _parse_response(content: str) -> dict:
        finish_match = re.search(r'finish\s*\(\s*message\s*=\s*"(.*?)"\s*\)', content, re.DOTALL)
        if finish_match:
            return {"name": FINISH, "reason": finish_match.group(1)}

        do_match = re.search(r'do\s*\(\s*action\s*=\s*(\w+)\s*\((.*?)\)\s*\)', content, re.DOTALL)
        if do_match:
            return ModelProvider._build_action(do_match.group(1), do_match.group(2))

        do_str_match = re.search(
            r'do\s*\(\s*action\s*=\s*"(\w+)"\s*,?\s*(.*?)\s*\)', content, re.DOTALL
        )
        if do_str_match:
            return ModelProvider._build_action(do_str_match.group(1), do_str_match.group(2))

        action_names = "|".join(ACTIONS)
        action_match = re.search(
            rf'\b({action_names})\s*\((.*?)\)', content, re.DOTALL
        )
        if action_match:
            return ModelProvider._build_action(action_match.group(1), action_match.group(2))

        tag_match = re.search(
            r'\[(Back|Home|Wait|Finish|LongPress|DoubleTap)\]', content
        )
        if tag_match:
            return {"name": tag_match.group(1)}

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        coord_match = re.search(r'[\(\[]\s*(\d{2,4})\s*,\s*(\d{2,4})\s*[\)\]]', content)
        if coord_match:
            return {"name": "Tap", "x": int(coord_match.group(1)), "y": int(coord_match.group(2))}

        raise ModelProviderError(f"cannot parse model reply: {content[-300:]!r}")

    @staticmethod
    def _build_action(action_name: str, params_str: str) -> dict:
        params = ModelProvider._parse_params(params_str)
        params.pop("action", None)
        for single, pair in (("element", ("x", "y")), ("start", ("x", "y")), ("end", ("x2", "y2"))):
            value = params.pop(single, None)
            if isinstance(value, list) and len(value) >= 2:
                params.setdefault(pair[0], value[0])
                params.setdefault(pair[1], value[1])
        if "message" in params and "reason" not in params:
            params["reason"] = params.pop("message")
        if not params and params_str.strip():
            parts = [p.strip() for p in params_str.split(",") if p.strip()]
            try:
                nums = [int(p) for p in parts]
            except ValueError:
                nums = []
            if action_name in ("Tap", "DoubleTap", "LongPress") and len(nums) >= 2:
                params["x"], params["y"] = nums[0], nums[1]
            elif action_name == "Swipe" and len(nums) >= 4:
                params["x"], params["y"] = nums[0], nums[1]
                params["x2"], params["y2"] = nums[2], nums[3]
        params["name"] = action_name
        return params

    @staticmethod
    def _parse_params(params_str: str) -> dict:
        result = {}
        pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\[([^\]]*)\]|(-?\d+))'
        for match in re.finditer(pattern, params_str):
            key = match.group(1)
            if match.group(2) is not None:
                result[key] = match.group(2)
            elif match.group(3) is not None:
                values = []
                for part in match.group(3).split(","):
                    part = part.strip().strip("\"'")
                    if not part:
                        continue
                    try:
                        values.append(int(part))
                    except ValueError:
                        values.append(part)
                result[key] = values
            elif match.group(4) is not None:
                result[key] = int(match.group(4))
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

    @staticmethod
    def extract_reasoning(payload: dict) -> str:
        return payload.get("_reasoning", "")


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
            result = dict(self._script.pop(0))
            result.setdefault("_reasoning", "")
            return result
        return {"name": FINISH, "reason": "script exhausted", "_reasoning": ""}

    def parse_action(self, payload: dict, display_id: int) -> Action:
        return ModelProvider.parse_action(payload, display_id)

    @staticmethod
    def extract_reasoning(payload: dict) -> str:
        return payload.get("_reasoning", "")
