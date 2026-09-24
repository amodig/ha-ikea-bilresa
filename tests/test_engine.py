"""Unit tests for the gesture engine (pure logic, no Home Assistant runtime)."""

from __future__ import annotations

import pytest

from custom_components.ikea_bilresa.const import (
    ACTION_HOLD,
    ACTION_PRESS,
    ACTION_RELEASE,
    ACTION_ROTATE,
    DIRECTION_DOWN,
    DIRECTION_UP,
    ROLE_BUTTON,
    ROLE_SCROLL_DOWN,
    ROLE_SCROLL_UP,
)
from custom_components.ikea_bilresa.engine import GestureEngine
from custom_components.ikea_bilresa.model import BilresaWheel, SwitchEndpoint

NODE = 12


@pytest.fixture
def wheel() -> BilresaWheel:
    return BilresaWheel(
        node_id=NODE,
        name="Test wheel",
        product_name="BILRESA scroll wheel",
        serial="SER123",
        endpoints={
            1: SwitchEndpoint(1, 1, ROLE_SCROLL_UP),
            2: SwitchEndpoint(2, 1, ROLE_SCROLL_DOWN),
            3: SwitchEndpoint(3, 1, ROLE_BUTTON),
        },
    )


def _decoded(endpoint_id: int, role: str, event_type: str, count=None) -> dict:
    return {
        "node_id": NODE,
        "wheel_name": "Test wheel",
        "endpoint_id": endpoint_id,
        "channel": 1,
        "role": role,
        "event_type": event_type,
        "count": count,
        "raw": {},
    }


def test_single_notch(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    action = engine.process(
        wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_complete", 1)
    )
    assert action is not None
    assert action.type == ACTION_ROTATE
    assert action.direction == DIRECTION_UP
    assert action.notches == 1


def test_cumulative_ongoing_yields_deltas(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    a1 = engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_ongoing", 6))
    a2 = engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_ongoing", 12))
    a3 = engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_complete", 18))
    assert [a1.notches, a2.notches, a3.notches] == [6, 6, 6]


def test_new_gesture_resets_after_complete(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_complete", 4))
    action = engine.process(
        wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_ongoing", 5)
    )
    assert action.notches == 5


def test_ongoing_counter_wrap_resets(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_ongoing", 8))
    # A lower count than last means a new gesture began.
    action = engine.process(
        wheel, _decoded(1, ROLE_SCROLL_UP, "multi_press_ongoing", 3)
    )
    assert action.notches == 3


def test_scroll_down_direction(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    action = engine.process(
        wheel, _decoded(2, ROLE_SCROLL_DOWN, "multi_press_complete", 2)
    )
    assert action.direction == DIRECTION_DOWN
    assert action.notches == 2


@pytest.mark.parametrize(
    ("endpoint", "role", "direction"),
    [(1, ROLE_SCROLL_UP, DIRECTION_UP), (2, ROLE_SCROLL_DOWN, DIRECTION_DOWN)],
)
def test_initial_notch_is_immediate_and_not_counted_twice(
    wheel: BilresaWheel, endpoint: int, role: str, direction: str
) -> None:
    engine = GestureEngine()
    for _ in range(2):
        action = engine.process(wheel, _decoded(endpoint, role, "initial_press"))
        assert action.type == ACTION_ROTATE
        assert action.direction == direction
        assert action.notches == 1
        for event, count in [
            ("short_release", None),
            ("multi_press_ongoing", 1),
            ("multi_press_complete", 1),
        ]:
            assert engine.process(wheel, _decoded(endpoint, role, event, count)) is None


def test_batched_scroll_with_repeated_initial_events(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    # InitialPress repeats during real wheel gestures; only the first is early.
    deltas = []
    for event, count in [
        ("initial_press", None),
        ("short_release", None),
        ("initial_press", None),
        ("multi_press_ongoing", 6),
        ("initial_press", None),
        ("multi_press_ongoing", 12),
        ("multi_press_ongoing", 12),
        ("multi_press_complete", 18),
    ]:
        action = engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, event, count))
        if action is not None:
            deltas.append(action.notches)
    assert deltas == [1, 5, 6, 6]


def test_early_notch_state_is_independent_and_resettable(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    for endpoint, role in [(1, ROLE_SCROLL_UP), (2, ROLE_SCROLL_DOWN)]:
        assert (
            engine.process(wheel, _decoded(endpoint, role, "initial_press")).notches
            == 1
        )
    engine.reset()
    assert (
        engine.process(wheel, _decoded(1, ROLE_SCROLL_UP, "initial_press")).notches == 1
    )
    assert engine.process(wheel, _decoded(3, ROLE_BUTTON, "initial_press")) is None


@pytest.mark.parametrize(("count", "presses"), [(1, 1), (2, 2), (3, 3)])
def test_button_click_counts(wheel: BilresaWheel, count: int, presses: int) -> None:
    engine = GestureEngine()
    action = engine.process(
        wheel, _decoded(3, ROLE_BUTTON, "multi_press_complete", count)
    )
    assert action.type == ACTION_PRESS
    assert action.presses == presses


def test_button_hold_and_release(wheel: BilresaWheel) -> None:
    engine = GestureEngine()
    hold = engine.process(wheel, _decoded(3, ROLE_BUTTON, "long_press"))
    release = engine.process(wheel, _decoded(3, ROLE_BUTTON, "long_release"))
    assert hold.type == ACTION_HOLD
    assert release.type == ACTION_RELEASE
