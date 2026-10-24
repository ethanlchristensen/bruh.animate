import pytest

from bruhanimate import (
    Buffer,
    DissolveImageEffect,
    FocusImageEffect,
    GlitchImageEffect,
    Scene,
)


def render(animation, width=20, height=10):
    frame = Buffer(height, width).clear_buffer(val=None)
    animation.draw(frame)
    return frame.buffer


@pytest.mark.parametrize(
    "kind", [GlitchImageEffect, FocusImageEffect, DissolveImageEffect]
)
def test_reverse_retraces_exact_seeded_frame_and_finishes_after_return(kind):
    options = (
        {"characters_per_second": 2, "travel_time": 0.5}
        if kind is GlitchImageEffect
        else {"duration": 2}
    )
    effect = kind("ABC", x=8, y=4, seed=42, reverse=True, hold_duration=1, **options)
    initial = render(effect)
    effect.update(0.5)
    entrance = render(effect)
    effect.update(2)
    assert render(effect)[4][8:11] == list("ABC")
    assert not effect.finished
    effect.update(2)
    assert render(effect) == entrance
    assert render(effect) == entrance  # Drawing never advances reverse time.
    assert not effect.finished
    effect.update(0.5)
    assert effect.finished
    assert render(effect) == initial
    effect.update(100)
    assert render(effect) == initial


@pytest.mark.parametrize(
    "kind", [GlitchImageEffect, FocusImageEffect, DissolveImageEffect]
)
def test_repeating_reverse_hides_only_after_exit_and_survives_resize_and_large_dt(kind):
    options = (
        {"characters_per_second": 2, "travel_time": 0.5}
        if kind is GlitchImageEffect
        else {"duration": 2}
    )
    effect = kind(
        "ABC",
        seed=42,
        repeat=True,
        reverse=True,
        hold_duration=1,
        repeat_delay=1,
        **options,
    )
    scene = Scene(effect)
    scene.start()
    try:
        scene.update(0.5)
        entrance = render(scene)
        scene.update(4)
        assert render(scene) == entrance
        scene.resize((1, 1))
        render(scene, 1, 1)
        scene.resize((20, 10))
        assert render(scene) == entrance
        scene.update(0.5)
        assert not any(cell is not None for row in render(scene) for cell in row)
        assert not scene.finished
        scene.update(1.5 + 6000)
        assert render(scene) == entrance
    finally:
        scene.close()


def test_reverse_dissolve_out_returns_to_full_image_and_fractional_ticks_finish():
    effect = DissolveImageEffect(
        "ABC", direction="out", duration=1, reverse=True, hold_duration=1, seed=7
    )
    initial = render(effect)
    effect.update(1.5)
    assert not any(cell is not None for row in render(effect) for cell in row)
    assert not effect.finished
    for _ in range(90):
        effect.update(1 / 60)
    assert effect.finished
    assert render(effect) == initial


@pytest.mark.parametrize(
    "kind", [GlitchImageEffect, FocusImageEffect, DissolveImageEffect]
)
def test_reverse_requires_boolean(kind):
    with pytest.raises(TypeError, match="reverse"):
        kind("ABC", reverse="yes")


def test_zero_hold_and_gap_reverses_without_skipping_the_endpoint():
    effect = DissolveImageEffect(
        "ABCD",
        duration=1,
        reverse=True,
        repeat=True,
        hold_duration=0,
        repeat_delay=0,
        seed=7,
    )
    effect.update(1)
    assert sum(cell is not None for row in render(effect) for cell in row) == 4
    effect.update(0.5)
    assert sum(cell is not None for row in render(effect) for cell in row) == 2
    effect.update(0.5)
    assert not any(cell is not None for row in render(effect) for cell in row)
