import pytest
from bruhcolor import bruhcolored

from bruhanimate import Buffer, GridViewport, draw_grid


def test_spacing_and_centering_share_one_coordinate_transform():
    buffer = Buffer(5, 9)
    grid = draw_grid(buffer, ["ab", "cd"], spacing=(2, 1))
    assert grid.to_screen(0, 0) == (3, 1)
    assert grid.to_screen(1, 1) == (5, 2)
    assert buffer.get_char(3, 1) == "a"
    assert buffer.get_char(4, 1) == " "
    assert buffer.get_char(5, 2) == "d"


def test_zero_coordinates_override_centering():
    buffer = Buffer(5, 9)
    grid = draw_grid(buffer, ["ab"], x=0, y=0)
    assert grid.to_screen(0, 0) == (0, 0)
    assert buffer.buffer[0][:2] == list("ab")


def test_oversized_boards_anchor_top_left_and_camera_selects_visible_cells():
    board = ["ABCDE", "FGHIJ"]
    buffer = Buffer(1, 3)
    grid = draw_grid(buffer, board)
    assert buffer.buffer == [list("ABC")]
    grid = draw_grid(buffer, board, camera=(1, 1))
    assert buffer.buffer == [list("GHI")]
    assert grid.to_screen(1, 1) == (0, 0)


def test_negative_origins_and_clipped_regions_preserve_outside_cells():
    buffer = Buffer(3, 3).clear_buffer(val=".")
    grid = draw_grid(buffer, ["123", "456", "789"], x=-1, y=-1, region=(-1, -1, 3, 3))
    assert buffer.buffer == [list("56."), list("89."), list("...")]
    assert not grid.put(0, 0, "X")
    assert not grid.put(3, 1, "X")


def test_empty_and_ragged_grids_have_explicit_behavior():
    buffer = Buffer(2, 2)
    draw_grid(buffer, [])
    draw_grid(buffer, [[], []])
    assert buffer.buffer == [[" ", " "], [" ", " "]]
    with pytest.raises(ValueError, match="rectangular"):
        draw_grid(buffer, ["ab", "c"])
    with pytest.raises(ValueError, match="shape"):
        GridViewport(buffer, 2, 2).draw(["ab"])


def test_mapping_supports_zero_color_spaces_and_transparent_cells():
    buffer = Buffer(1, 3).clear_buffer(val=".")
    black = bruhcolored("#", color=0).colored
    draw_grid(buffer, [[0, 1, 2]], glyph={0: black, 1: " ", 2: None})
    assert buffer.buffer == [[black, " ", "."]]


def test_only_visible_cells_invoke_the_glyph_callback():
    buffer = Buffer(2, 3)
    calls = []

    def glyph(value, col, row):
        calls.append((col, row))
        return value

    draw_grid(buffer, ["X" * 100] * 100, camera=(50, 50), glyph=glyph)
    assert calls == [(x, y) for y in (50, 51) for x in (50, 51, 52)]
    assert buffer.buffer == [list("XXX"), list("XXX")]


def test_path_markers_and_text_use_grid_spacing_and_clip_to_region():
    buffer = Buffer(3, 9).clear_buffer(val=".")
    grid = GridViewport(buffer, 5, 2, x=0, y=1, spacing=(2, 1), region=(0, 1, 7, 2))
    grid.path([(0, 0), (1, 0), (4, 0)], "*")
    grid.text(1, 1, "ABCDE")
    assert buffer.buffer[0] == list(".........")
    assert buffer.buffer[1] == list("*.*......")
    assert buffer.buffer[2] == list("..A.B.C..")


@pytest.mark.parametrize(
    "glyph", ["", "ab", "\n", "\t", "\x1b[2J", "界", "e\u0301", "\u0301", "\ufe0f"]
)
def test_non_single_cell_glyphs_are_rejected(glyph):
    with pytest.raises(ValueError, match="single-cell"):
        GridViewport(Buffer(1, 1), 1, 1).put(0, 0, glyph)


@pytest.mark.parametrize(
    "layout",
    [
        {"columns": -1},
        {"rows": -1},
        {"spacing": (0, 1)},
        {"spacing": (1, -1)},
        {"region": (0, 0, -1, 2)},
    ],
)
def test_invalid_layouts_fail_at_construction(layout):
    options = {"columns": 1, "rows": 1, **layout}
    with pytest.raises(ValueError):
        GridViewport(Buffer(1, 1), **options)
