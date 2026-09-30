from __future__ import annotations

import pytest

from wellphone.agent.action_space import BACK, FINISH, SWIPE, TAKE_OVER, TAP, TYPE
from wellphone.agent.model_provider import ModelProvider, ModelProviderError


def _parse(content: str) -> dict:
    return ModelProvider._parse_response(content)


def test_finish_message() -> None:
    assert _parse('finish(message="任务完成")') == {"name": FINISH, "reason": "任务完成"}


def test_nested_function_call() -> None:
    assert _parse("do(action=Tap(x=540, y=960))") == {"name": TAP, "x": 540, "y": 960}


def test_string_action_with_message() -> None:
    out = _parse('do(action="Take_over", message="敏感页面")')
    assert out == {"name": TAKE_OVER, "reason": "敏感页面"}


def test_element_coordinates() -> None:
    out = _parse('do(action="Tap", element=[139, 134])')
    assert out == {"name": TAP, "x": 139, "y": 134}


def test_bare_function_call() -> None:
    out = _parse("Let me tap it.\nTap(499, 620)")
    assert out == {"name": TAP, "x": 499, "y": 620}


def test_bracket_tag() -> None:
    assert _parse("I need to go back.\n[Back]") == {"name": BACK}


def test_string_action_text() -> None:
    out = _parse('do(action="Type", text="hello world")')
    assert out == {"name": TYPE, "text": "hello world"}


def test_swipe_start_end() -> None:
    out = _parse('do(action="Swipe", start=[100, 200], end=[300, 400])')
    assert out == {"name": SWIPE, "x": 100, "y": 200, "x2": 300, "y2": 400}


def test_unknown_format_raises() -> None:
    with pytest.raises(ModelProviderError):
        _parse("I am thinking about what to do next.")
