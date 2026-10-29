import pytest

from bruhanimate import Buffer, draw_ellipse, draw_line, draw_rect


@pytest.mark.parametrize("end", [(x, y) for x in range(-3, 4) for y in range(-3, 4)])
def test_lines_are_endpoint_symmetric_and_clip_like_a_crop(end):
    start = (4, 4)
    end = (end[0] + 4, end[1] + 4)
    full, reverse, clipped = Buffer(9, 9), Buffer(9, 9), Buffer(9, 9)
    draw_line(full, start, end)
    draw_line(reverse, end, start)
    draw_line(clipped, start, end, clip=(3, 3, 3, 3))
    assert full.buffer == reverse.buffer
    assert full.get_char(*start) == full.get_char(*end) == "#"
    for y in range(9):
        for x in range(9):
            assert clipped.get_char(x, y) == (
                full.get_char(x, y) if 3 <= x < 6 and 3 <= y < 6 else " "
            )


@pytest.mark.parametrize("draw", [draw_rect, draw_ellipse])
@pytest.mark.parametrize("filled", [True, False])
def test_shape_clipping_preserves_original_outline(draw, filled):
    full, clipped = Buffer(9, 11), Buffer(9, 11)
    draw(full, (1, 1, 9, 7), filled=filled)
    draw(clipped, (1, 1, 9, 7), filled=filled, clip=(4, 3, 3, 2))
    for y in range(9):
        for x in range(11):
            assert clipped.get_char(x, y) == (
                full.get_char(x, y) if 4 <= x < 7 and 3 <= y < 5 else " "
            )


def test_huge_offscreen_shapes_only_visit_viewport():
    huge = 10**100
    buffer = Buffer(3, 5)
    draw_line(buffer, (-huge, 1), (huge, 1))
    assert buffer.buffer[1] == ["#"] * 5
    draw_rect(buffer, (-huge, -huge, 2 * huge, 2 * huge), "R")
    assert buffer.buffer[0] == [" "] * 5  # no invented clipping border
    draw_ellipse(buffer, (-huge, -huge, 2 * huge, 2 * huge), "E", filled=True)
    assert buffer.buffer == [["E"] * 5 for _ in range(3)]


@pytest.mark.parametrize("draw", [draw_rect, draw_ellipse])
@pytest.mark.parametrize("bounds", [(0, 0, 0, 5), (0, 0, 5, 0), (8, 8, 3, 3)])
def test_empty_and_offscreen_shapes_paint_nothing(draw, bounds):
    buffer = Buffer(3, 5)
    draw(buffer, bounds)
    assert buffer.buffer == [[" "] * 5 for _ in range(3)]


@pytest.mark.parametrize("draw", [draw_rect, draw_ellipse])
def test_degenerate_shapes_and_ansi_cells(draw):
    buffer = Buffer(1, 1)
    glyph = "\x1b[31mX\x1b[0m"
    draw(buffer, (0, 0, 1, 1), glyph)
    assert buffer.get_char(0, 0) == glyph


@pytest.mark.parametrize("glyph", ["XX", "\t", "界", "e\u0301", "\x1b[2JX"])
def test_shapes_reject_unsupported_glyphs(glyph):
    with pytest.raises((TypeError, ValueError)):
        draw_line(Buffer(1, 1), (0, 0), (0, 0), glyph)


@pytest.mark.parametrize(
    "bounds", [(0, 0, -1, 2), (0, 0, 2.0, 2), (False, 0, 2, 2), [0, 0, 2, 2]]
)
def test_invalid_geometry_does_not_paint(bounds):
    buffer = Buffer(3, 3)
    with pytest.raises((TypeError, ValueError)):
        draw_rect(buffer, bounds)
    assert buffer.buffer == [[" "] * 3 for _ in range(3)]
