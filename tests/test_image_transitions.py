import pytest

from bruhanimate import Buffer, DissolveImageEffect, FocusImageEffect, Scene
from bruhanimate.demos._image_cycle import ImageCycle


def render(effect, width=30, height=12):
    frame = Buffer(height, width).clear_buffer(val=None)
    effect.draw(frame)
    return frame.buffer


def count(frame):
    return sum(cell is not None for row in frame for cell in row)


def test_focus_converges_from_scatter_and_keeps_draw_pure():
    effect = FocusImageEffect(
        ["ABC", " D "], x=10, y=5, duration=2, scatter=(5, 3), seed=42
    )
    first = render(effect)
    assert first == render(effect)
    effect.update(1)
    middle = render(effect)
    assert middle != first
    effect.update(1)
    settled = render(effect)
    assert settled[5][10:13] == list("ABC")
    assert settled[6][11] == "D"
    assert count(settled) == 4
    assert effect.finished
    effect.update(100)
    assert render(effect) == settled
    assert first != settled


@pytest.mark.parametrize("direction", ["in", "out"])
def test_dissolve_has_random_order_and_exact_in_out_endpoints(direction):
    effect = DissolveImageEffect(
        "ABCDEFGHIJ", x=0, y=0, direction=direction, duration=2, seed=42
    )
    assert count(render(effect)) == (0 if direction == "in" else 10)
    effect.update(1)
    middle = render(effect)
    assert count(middle) == 5
    assert middle[0][:5] != list("ABCDE")
    assert not effect.finished
    effect.update(1)
    assert count(render(effect)) == (10 if direction == "in" else 0)
    assert effect.finished
    assert render(effect) == render(effect)


@pytest.mark.parametrize("kind", [FocusImageEffect, DissolveImageEffect])
def test_seeded_transitions_preserve_state_through_resize_and_update_partition(kind):
    one = kind("ABCDEFGHIJ", duration=2, seed=42)
    many = kind("ABCDEFGHIJ", duration=2, seed=42)
    different = kind("ABCDEFGHIJ", duration=2, seed=43)
    one.update(1)
    different.update(1)
    for _ in range(4):
        many.update(0.25)
        render(many)
    assert render(one) == render(many)
    assert render(one) != render(different)
    scene = Scene(one)
    scene.start()
    try:
        before = render(scene)
        scene.resize((1, 1))
        assert len(render(scene, 1, 1)[0]) == 1
        scene.resize((30, 12))
        assert render(scene) == before
    finally:
        scene.close()


@pytest.mark.parametrize("kind", [FocusImageEffect, DissolveImageEffect])
def test_transition_repeats_hold_gap_large_steps_and_empty_images(kind):
    effect = kind(
        "AB", duration=1, repeat=True, hold_duration=2, repeat_delay=1, seed=42
    )
    effect.update(4001)
    assert count(render(effect)) == 2
    assert not effect.finished
    effect.update(2)
    assert count(render(effect)) == 0
    effect.update(2)
    assert count(render(effect)) == 2
    effect.close()
    effect.close()
    assert kind([], repeat=True).finished


@pytest.mark.parametrize("kind", [FocusImageEffect, DissolveImageEffect])
@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"duration": 0}, ValueError),
        ({"duration": -1}, ValueError),
        ({"duration": float("inf")}, ValueError),
        ({"duration": float("nan")}, ValueError),
        ({"duration": True}, TypeError),
        ({"seed": "42"}, TypeError),
        ({"repeat": 1}, TypeError),
        ({"hold_duration": -1}, ValueError),
        ({"repeat_delay": float("nan")}, ValueError),
        ({"x": float("inf")}, ValueError),
    ],
)
def test_transition_validation(kind, kwargs, error):
    with pytest.raises(error):
        kind("X", **kwargs)


@pytest.mark.parametrize(
    "scatter, error",
    [
        ((-1, 2), ValueError),
        ((1.2, 3), TypeError),
        ((True, 3), TypeError),
        ([1, 2], TypeError),
    ],
)
def test_focus_scatter_validation(scatter, error):
    with pytest.raises(error):
        FocusImageEffect("X", scatter=scatter)


def test_direction_validation_and_zero_scatter():
    with pytest.raises(ValueError, match="direction"):
        DissolveImageEffect("X", direction="sideways")
    effect = FocusImageEffect("X", scatter=(0, 0))
    before = render(effect)
    effect.update(2)
    assert render(effect) == before


def test_demo_cycle_visits_each_effect_closes_replaced_child_and_wraps(monkeypatch):
    cycle = ImageCycle(["AB"])
    cycle.start()
    old = cycle.current
    calls = []
    monkeypatch.setattr(old, "close", lambda: calls.append("closed"))
    cycle.update(2 * old.duration + 4)
    assert calls == ["closed"]
    assert cycle.phase_name == "Focus"
    focus = cycle.current
    cycle.update(2 * focus.duration + 4)
    assert cycle.phase_name == "Dissolve"
    cycle.update(2 * cycle.current.duration + 4)
    assert cycle.phase_name == "Wipe"
    cycle.update(2 * cycle.current.duration + 4)
    assert cycle.phase_name == "Glitch"
    assert cycle.current is not old
    cycle.update(1000 * sum(cycle._lengths) + 0.5)
    assert cycle.phase_name == "Glitch"
    first = render(cycle)
    assert first == render(cycle)
    cycle.close()
    cycle.close()
