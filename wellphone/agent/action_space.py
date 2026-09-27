from __future__ import annotations

from dataclasses import dataclass

LAUNCH = "Launch"
TAP = "Tap"
TYPE = "Type"
SWIPE = "Swipe"
BACK = "Back"
HOME = "Home"
LONG_PRESS = "LongPress"
DOUBLE_TAP = "DoubleTap"
WAIT = "Wait"
TAKE_OVER = "Take_over"
FINISH = "Finish"

ACTIONS = (
    LAUNCH,
    TAP,
    TYPE,
    SWIPE,
    BACK,
    HOME,
    LONG_PRESS,
    DOUBLE_TAP,
    WAIT,
    TAKE_OVER,
    FINISH,
)


@dataclass(frozen=True)
class Action:
    name: str
    display_id: int
    x: int | None = None
    y: int | None = None
    x2: int | None = None
    y2: int | None = None
    text: str | None = None
    package: str | None = None
    reason: str | None = None
    duration_ms: int = 300

    def to_dict(self) -> dict:
        return {
            k: v
            for k, v in self.__dict__.items()
            if v is not None and k != "display_id"
        } | {"display_id": self.display_id}
