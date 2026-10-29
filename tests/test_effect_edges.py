"""Boundary and settings-isolation regressions from the package review."""

import pytest

from bruhanimate import (
    Buffer,
    DrawLinesEffect,
    DrawLinesSettings,
    Line,
    RainEffect,
    RainSettings,
    TwinkleEffect,
    TwinkleSettings,
    VoronoiEffect,
    VoronoiSettings,
)


@pytest.mark.parametrize("count", [127, 128, 129, 256])
def test_voronoi_site_indices_survive_update_and_resize(count):
    effect = VoronoiEffect(Buffer(4, 5), " ", VoronoiSettings(num_seeds=count, seed=1))
    effect.start()
    try:
        effect.update(1 / 30)
        effect.resize((7, 3))
        effect.update(1 / 30)
        first, second = Buffer(3, 7), Buffer(3, 7)
        effect.draw(first)
        effect.draw(second)
        assert first.buffer == second.buffer
        assert all(isinstance(cell, str) for row in first.buffer for cell in row)
        assert effect._seeds.shape == (count, 4)
    finally:
        effect.close()


@pytest.mark.parametrize("setter", [False, True])
def test_twinkle_copies_explicit_characters_before_resize(setter):
    chars = ["*"]
    settings = TwinkleSettings(density=1, twinkle_chars=chars, seed=1)
    effect = TwinkleEffect(Buffer(1, 1), " ", settings)
    if setter:
        effect.set_twinkle_chars(chars)
    chars.clear()
    effect.resize((2, 1))
    effect.update(1 / 30)
    assert [cell.char for cell in effect.buffer.buffer[0]] == ["*", "*"]
    effect.close()


@pytest.mark.parametrize(
    "chars,error",
    [
        ([], ValueError),
        (["XX"], ValueError),
        (["界"], ValueError),
        (["\x1b"], ValueError),
        ([1], TypeError),
        ("*", TypeError),
    ],
)
def test_invalid_twinkle_replacement_preserves_raster_and_random_stream(chars, error):
    effect = TwinkleEffect(Buffer(2, 3), " ", TwinkleSettings(density=1, seed=5))
    before = [[str(cell) for cell in row] for row in effect.buffer.buffer]
    random_state = effect.rng.getstate()
    with pytest.raises(error):
        effect.set_twinkle_chars(chars)
    assert effect.twinkle_chars == ["."]
    assert [[str(cell) for cell in row] for row in effect.buffer.buffer] == before
    assert effect.rng.getstate() == random_state
    effect.update(1 / 30)
    effect.close()


@pytest.mark.parametrize(
    "outside",
    [((-3, 1), (-1, 3)), ((10, 1), (10, 3)), ((1, -4), (3, -4)), ((1, 5), (4, 5))],
)
@pytest.mark.parametrize("first", [False, True])
def test_offscreen_segment_does_not_hide_other_lines(outside, first):
    visible = ((1, 2), (4, 2))
    expected = DrawLinesEffect(Buffer(5, 10), " ", DrawLinesSettings(char="#"))
    expected.add_line(*visible)
    expected.update(1 / 30)
    effect = DrawLinesEffect(Buffer(5, 10), " ", DrawLinesSettings(char="#"))
    for endpoints in [outside, visible] if first else [visible, outside]:
        effect.add_line(*endpoints)
    effect.update(1 / 30)
    assert effect.buffer.buffer == expected.buffer.buffer
    assert "#" in effect.buffer.buffer[2]


@pytest.mark.parametrize("endpoints", [((-2, 2), (4, 2)), ((2, -2), (2, 4))])
def test_segments_crossing_viewport_are_still_drawn(endpoints):
    effect = DrawLinesEffect(Buffer(5, 6), " ", DrawLinesSettings(char="#"))
    effect.add_line(*endpoints)
    effect.update(1 / 30)
    assert any("#" in row for row in effect.buffer.buffer)


def test_line_update_uses_same_cell_coordinates_as_construction():
    line = Line((2, 2), (4, 4))
    for start, end in [((2, 2), (4, 4)), ((-1, 0), (5, 3)), ((1, 1), (3, 2))]:
        line.update_points(start, end)
        fresh = Line(start, end)
        assert line.get_points() == fresh.get_points()
        updated = DrawLinesEffect(Buffer(5, 6), " ")
        expected = DrawLinesEffect(Buffer(5, 6), " ")
        updated.lines.append(line)
        expected.lines.append(fresh)
        updated.update(1 / 30)
        expected.update(1 / 30)
        assert updated.buffer.buffer == expected.buffer.buffer


@pytest.mark.parametrize(
    "wind,expected", [("east", "   X "), ("west", " X   "), ("none", "  X  ")]
)
def test_rain_wind_keeps_direction_after_buffer_rotation_fix(wind, expected):
    effect = RainEffect(
        Buffer(3, 5), " ", RainSettings(intensity=0, wind_direction=wind)
    )
    effect.update(1 / 30)
    effect.buffer.put_at(0, 0, "  X  ")
    effect.update(1 / 30)
    assert "".join(effect.buffer.buffer[1]) == expected
