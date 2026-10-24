import pytest

from bruhanimate import Buffer, GlitchImageEffect, Scene


def render(image, width=16, height=7):
    buffer = Buffer(height, width)
    buffer.clear_buffer(val=None)
    image.draw(buffer)
    return buffer.buffer


def test_glyph_flies_changes_symbols_then_settles_without_draw_side_effects():
    image = GlitchImageEffect(
        "    A", x=3, y=3, characters_per_second=10, travel_time=1, seed=42
    )
    image.start()
    assert not any(cell for row in render(image) for cell in row)
    image.update(0.4)
    first = render(image)
    assert first == render(image)
    flying = [
        (x, y, char)
        for y, row in enumerate(first)
        for x, char in enumerate(row)
        if char is not None
    ]
    assert len(flying) == 1
    x, y, char = flying[0]
    assert 2 <= x < 7 and 2 <= y <= 4 and char != "A"
    image.update(0.1)
    assert render(image) != first
    assert not image.finished
    image.update(0.6)
    assert image.finished
    settled = render(image)
    assert settled[3][7] == "A"
    assert sum(cell is not None for row in settled for cell in row) == 1
    image.update(20)
    image.start()
    assert render(image) == settled
    image.close()
    image.close()


def test_launch_order_is_left_to_right_and_settled_glyphs_win_collisions():
    image = GlitchImageEffect(
        ["A B", "C"], x=3, y=3, characters_per_second=2, travel_time=1, seed=1
    )
    image.update(1.5)
    frame = render(image)
    assert frame[3][3] == "A"
    assert not image.finished
    image.update(1)
    frame = render(image)
    assert image.finished
    assert frame[3][3:6] == ["A", None, "B"]
    assert frame[4][3] == "C"


def test_seed_and_time_are_independent_of_presentation_and_update_counts():
    one = GlitchImageEffect("  ABCD", x=3, y=3, seed=23)
    many = GlitchImageEffect("  ABCD", x=3, y=3, seed=23)
    one.update(0.5)
    for _ in range(4):
        many.update(0.125)
        render(many)
        render(many)
    assert render(one) == render(many)
    different = GlitchImageEffect("  ABCD", x=3, y=3, seed=24)
    different.update(0.5)
    assert render(one) != render(different)


def test_resize_clips_and_recenters_without_resetting_flight():
    image = GlitchImageEffect("ABC", seed=7)
    scene = Scene(image)
    scene.start()
    try:
        scene.update(0.5)
        first = render(scene)
        scene.resize((1, 1))
        assert len(render(scene, 1, 1)[0]) == 1
        scene.resize((16, 7))
        assert render(scene) == first
        scene.update(1)
        assert scene.finished
        assert render(scene)[3][6:9] == list("ABC")
    finally:
        scene.close()


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"characters_per_second": 0}, ValueError),
        ({"characters_per_second": None}, TypeError),
        ({"travel_time": 0}, ValueError),
        ({"travel_time": -1}, ValueError),
        ({"travel_time": float("nan")}, ValueError),
        ({"travel_time": float("inf")}, ValueError),
        ({"travel_time": True}, TypeError),
        ({"seed": True}, TypeError),
        ({"seed": "42"}, TypeError),
    ],
)
def test_invalid_options(kwargs, error):
    with pytest.raises(error):
        GlitchImageEffect("A", **kwargs)


def test_empty_image_and_invalid_dt():
    empty = GlitchImageEffect(["   "])
    assert empty.finished
    assert not any(cell for row in render(empty) for cell in row)
    with pytest.raises(ValueError, match="dt"):
        empty.update(-1)


def test_fractional_ticks_complete_and_large_dt_settles_all_glyphs():
    image = GlitchImageEffect("ABC", characters_per_second=3, travel_time=1)
    for _ in range(120):
        image.update(1 / 60)
    assert image.finished
    other = GlitchImageEffect("ABC", characters_per_second=3, travel_time=1)
    other.update(100)
    assert render(other) == render(image)


def test_repeat_holds_disappears_and_restarts_the_same_seeded_entrance():
    image = GlitchImageEffect(
        " A",
        x=3,
        y=3,
        characters_per_second=2,
        travel_time=0.5,
        repeat=True,
        hold_duration=3,
        repeat_delay=1,
        seed=42,
    )
    image.update(0.75)
    entrance = render(image)
    image.update(0.25)
    settled = render(image)
    assert settled[3][4] == "A"
    assert not image.finished
    image.update(2.99)
    assert render(image) == settled
    image.update(0.01)
    assert not any(cell for row in render(image) for cell in row)
    image.update(0.75)
    assert not any(cell for row in render(image) for cell in row)
    image.update(1)
    assert render(image) == entrance
    assert not image.finished
    assert settled[3][4] == "A"


def test_repeat_large_updates_and_resize_keep_cycle_phase():
    image = GlitchImageEffect(
        " A",
        characters_per_second=2,
        travel_time=0.5,
        repeat=True,
        hold_duration=3,
        repeat_delay=1,
        seed=7,
    )
    scene = Scene(image)
    scene.start()
    try:
        scene.update(5001)
        assert render(scene)[3][8] == "A"
        assert not scene.finished
        scene.update(3)
        assert not any(cell for row in render(scene) for cell in row)
        scene.resize((1, 1))
        render(scene, 1, 1)
        scene.resize((16, 7))
        assert not any(cell for row in render(scene) for cell in row)
        scene.update(2)
        assert render(scene)[3][8] == "A"
        assert not scene.finished
    finally:
        scene.close()


def test_repeat_with_no_hold_or_gap_and_fractional_ticks():
    image = GlitchImageEffect(
        " A",
        characters_per_second=2,
        travel_time=0.5,
        repeat=True,
        hold_duration=0,
        repeat_delay=0,
        seed=7,
    )
    for _ in range(60):
        image.update(1 / 60)
    assert not any(cell for row in render(image) for cell in row)
    assert not image.finished
    image.update(0.75)
    assert any(cell for row in render(image) for cell in row)


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"repeat": 1}, TypeError),
        ({"hold_duration": -1}, ValueError),
        ({"repeat_delay": float("inf")}, ValueError),
        ({"hold_duration": float("nan")}, ValueError),
        ({"repeat_delay": True}, TypeError),
    ],
)
def test_invalid_cycle_options(kwargs, error):
    with pytest.raises(error):
        GlitchImageEffect("A", **kwargs)
