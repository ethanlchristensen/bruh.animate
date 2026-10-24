import re
from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from bruhanimate import (
    Animation,
    Buffer,
    CallbackEffect,
    ImageEffect,
    ImageMask,
    Layer,
    Scene,
    TextStyle,
)


def draw(scene, width=5, height=3):
    buffer = Buffer(height, width).clear_buffer(val=".")
    scene.draw(buffer)
    return buffer


def plain(buffer):
    return [
        "".join(re.sub(r"\x1b\[[0-9;:]*m", "", str(c)) for c in row)
        for row in buffer.buffer
    ]


def test_mask_centers_ragged_rows_and_intersects_region_after_resize():
    mask = ImageMask(["###", "#"])
    scene = Scene(
        Layer(
            CallbackEffect(lambda b: b.clear_buffer(val="X")),
            mask=mask,
            region=(2, 0, 10, 10),
        )
    )
    assert plain(draw(scene)) == ["..XX.", ".....", "....."]
    scene.resize((7, 5))
    assert plain(draw(scene, 7, 5)) == [
        ".......",
        "..XXX..",
        "..X....",
        ".......",
        ".......",
    ]


def test_image_mask_snapshots_rows_and_inversion_includes_outside():
    rows = ["# #"]
    mask = ImageMask(rows, x=-1, y=0, invert=True)
    rows[0] = "   "
    assert [mask(x, 0, (4, 1)) for x in range(4)] == [True, False, True, True]
    assert mask.rows == ("# #",)
    with pytest.raises(FrozenInstanceError):
        mask.x = 4
    assert not ImageMask([])(0, 0, (1, 1))
    assert ImageMask([], invert=True)(0, 0, (1, 1))


def test_custom_mask_coordinates_and_hidden_child_lifecycle():
    child = Mock(spec=Animation)
    child.draw.side_effect = lambda b: b.put_char(1, 1, "X")
    seen = []

    def mask(x, y, size):
        seen.append((x, y, size))
        return False

    scene = Scene(Layer(child, mask=mask))
    scene.start()
    scene.update(0.5)
    assert plain(draw(scene)) == ["....."] * 3
    scene.resize((6, 4))
    draw(scene, 6, 4)
    scene.close()
    scene.close()
    assert seen == [(1, 1, (5, 3)), (1, 1, (6, 4))]
    child.start.assert_called_once()
    child.update.assert_called_once_with(0.5)
    child.close.assert_called_once()


@pytest.mark.parametrize(
    "background, expected",
    [
        ("\x1b[41m \x1b[0m", "\x1b[41m"),
        ("\x1b[104m \x1b[0m", "\x1b[104m"),
        ("\x1b[48;5;0m \x1b[0m", "\x1b[48;5;0m"),
        ("\x1b[48;2;0;42;99m \x1b[0m", "\x1b[48;2;0;42;99m"),
        ("\x1b[48:2::0:42:99m \x1b[0m", "\x1b[48:2::0:42:99m"),
        ("\x1b[48;5;100;38;2;0;0;0m \x1b[0m", "\x1b[48;5;100m"),
        ("\x1b[41m\x1b[0mX", "\x1b[49m"),
        ("\x1b[41;49mX", "\x1b[49m"),
        (" ", "\x1b[49m"),
        (None, "\x1b[49m"),
    ],
)
def test_preserve_background_resolves_color_at_glyph_without_copying_attributes(
    background, expected
):
    scene = Scene(
        CallbackEffect(lambda b: b.put_char(0, 0, background)),
        Layer(
            ImageEffect("A", x=0, y=0),
            style=TextStyle(foreground=231, bold=True),
            preserve_background=True,
        ),
    )
    frame = Buffer(1, 1).clear_buffer(val=None)
    scene.draw(frame)
    assert frame.get_char(0, 0) == expected + "\x1b[1;38;5;231mA\x1b[0m"


def test_style_and_background_follow_live_composition_and_leave_old_frames_unchanged():
    lower = {"color": 20}
    scene = Scene(
        CallbackEffect(
            lambda b: b.clear_buffer(val=f"\x1b[48;5;{lower['color']}m \x1b[0m")
        ),
        Layer(
            ImageEffect("A B", x=0, y=0),
            transparent=True,
            style=TextStyle(foreground=231),
            preserve_background=True,
        ),
    )
    first = draw(scene, 3, 1)
    lower["color"] = 30
    second = draw(scene, 3, 1)
    assert "48;5;20m" in first.get_char(0, 0)
    assert "48;5;30m" in second.get_char(0, 0)
    assert second.get_char(1, 0) == "\x1b[48;5;30m \x1b[0m"
    assert draw(scene, 3, 1).buffer == second.buffer


def test_explicit_style_background_wins_and_child_foreground_is_retained():
    scene = Scene(
        Layer(
            CallbackEffect(lambda b: b.put_char(0, 0, "\x1b[31;44mX\x1b[0m")),
            style=TextStyle(background=7),
            preserve_background=True,
        )
    )
    assert draw(scene, 1, 1).get_char(0, 0) == "\x1b[31;44m\x1b[48;5;7mX\x1b[0m"


@pytest.mark.parametrize(
    "kwargs", [{"mask": 3}, {"style": "red"}, {"preserve_background": 1}]
)
def test_invalid_layer_options(kwargs):
    with pytest.raises(TypeError):
        Layer(ImageEffect("x"), **kwargs)


@pytest.mark.parametrize("kwargs", [{"x": True}, {"y": 1.5}, {"invert": 1}])
def test_invalid_mask_options(kwargs):
    with pytest.raises(TypeError):
        ImageMask("x", **kwargs)


@pytest.mark.parametrize("text", ["\x1b[31mx", "界", "e\u0301", "\t"])
def test_mask_rejects_non_cell_text(text):
    with pytest.raises(ValueError):
        ImageMask([text])
