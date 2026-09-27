from __future__ import annotations

from wellphone.agent.action_space import Action
from wellphone.agent.model_provider import ModelProvider


class VlmAgent:
    def __init__(self, provider: ModelProvider, display_id: int):
        self._provider = provider
        self._display_id = display_id

    def decide(
        self,
        task: str,
        screenshot_png: bytes | None = None,
        ui_dump: str = "",
        history: list[str] | None = None,
    ) -> Action:
        payload = self._provider.decide(
            task, screenshot_png, ui_dump, list(history or [])
        )
        return self._provider.parse_action(payload, self._display_id)
