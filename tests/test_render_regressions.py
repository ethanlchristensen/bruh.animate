"""Rendering behavior across independent clocks and optimized composition."""

import random

import pytest
from bruhcolor import bruhcolored

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Layer,
    MatrixEffect,
    MatrixSettings,
    Panel,
    Scene,
)


def test_matrix_character_clock_paints_without_advancing_color_clock():
    effect = MatrixEffect(
        Buffer(2, 12),
        " ",
        MatrixSettings(
            seed=42,
            character_halt_range=(1, 1),
            color_halt_range=(1, 1),
            character_randomness_one=1,
            character_randomness_two=1,
            color_randomness=0,
        ),
    )
    effect.start()
    try:
        effect.update(1 / 30)
        original = Buffer(2, 12)
        effect.draw(original)
        for _ in range(5):
            effect.update(1 / 30)
        final = Buffer(2, 12)
        effect.draw(final)
        assert final.buffer != original.buffer
        assert effect._MatrixEffect__color_ticks == [0, 0]
        for y, row in enumerate(final.buffer):
            for x, cell in enumerate(row):
                character = effect._MatrixEffect__buffer_characters[y][x]
                assert f"m{character}\x1b[0m" in cell
        before = effect.rng.getstate()
        repeat = Buffer(2, 12)
        effect.draw(repeat)
        assert repeat.buffer == final.buffer
        assert effect.rng.getstate() == before
    finally:
        effect.close()


def test_matrix_color_clock_paints_without_character_changes():
    effect = MatrixEffect(
        Buffer(2, 12),
        " ",
        MatrixSettings(
            seed=42,
            color_halt_range=(1, 1),
            character_randomness_one=0,
            color_randomness=1,
        ),
    )
    try:
        effect.update(1 / 30)
        characters = [row[:] for row in effect._MatrixEffect__buffer_characters]
        first = Buffer(2, 12)
        effect.draw(first)
        effect.update(1 / 30)
        second = Buffer(2, 12)
        effect.draw(second)
        assert first.buffer != second.buffer
        assert characters == effect._MatrixEffect__buffer_characters
        assert effect._MatrixEffect__color_ticks == [1, 1]
    finally:
        effect.close()


def test_matrix_styling_tracks_palette_and_environment_between_ticks(monkeypatch):
    effect = MatrixEffect(
        Buffer(4, 20),
        " ",
        MatrixSettings(seed=2, color_halt_range=(1, 1), color_randomness=1),
    )
    try:
        effect.update(1 / 30)
        for disabled, palette in (
            (False, [22, 46]),
            (True, [100]),
            (False, [120, 232]),
        ):
            if disabled:
                monkeypatch.setenv("ANSI_COLORS_DISABLED", "1")
            else:
                monkeypatch.delenv("ANSI_COLORS_DISABLED", raising=False)
            effect.set_gradient(palette)
            effect.update(1 / 30)
            frame = Buffer(4, 20)
            effect.draw(frame)
            for y, row in enumerate(frame.buffer):
                for x, cell in enumerate(row):
                    color = palette[
                        (x - effect._MatrixEffect__color_ticks[y]) % len(palette)
                    ]
                    assert (
                        cell
                        == bruhcolored(
                            effect._MatrixEffect__buffer_characters[y][x], color=color
                        ).colored
                    )
    finally:
        effect.close()


@pytest.mark.parametrize("seed", range(8))
def test_composition_matches_cell_oracle_for_clipping_and_transparency(seed):
    rng = random.Random(seed)
    width, height = 17, 11
    expected = [["."] * width for _ in range(height)]
    layers = []
    for _ in range(10):
        pixels = [
            [
                rng.choice([None, None, " ", "X", "\x1b[31m \x1b[0m", 0])
                for _ in range(width)
            ]
            for _ in range(height)
        ]
        # Include wholly transparent rows between painted rows.
        pixels[rng.randrange(height)] = [None] * width
        x, y = rng.randrange(-5, width), rng.randrange(-5, height)
        w, h = rng.randrange(20), rng.randrange(15)
        transparent = rng.choice([False, True])

        def paint(buffer, pixels=pixels):
            assert all(cell is None for row in buffer.buffer for cell in row)
            buffer.buffer = [row[:] for row in pixels]

        layers.append(
            Layer(CallbackEffect(paint), region=(x, y, w, h), transparent=transparent)
        )
        for row in range(height):
            for col in range(width):
                cell = pixels[row][col]
                if x <= col < x + w and y <= row < y + h and cell is not None:
                    if not (transparent and str(cell) == " "):
                        expected[row][col] = str(cell)
    scene = Scene(*layers)
    frame = Buffer(height, width).clear_buffer(val=".")
    scene.draw(frame)
    assert frame.buffer == expected
    retained = [row[:] for row in frame.buffer]
    scene.draw(Buffer(height, width))
    assert frame.buffer == retained


def test_moving_overlapping_panels_erase_old_footprints_after_resize():
    first = Panel(
        CallbackEffect(lambda b: b.clear_buffer(val="A")),
        size=(3, 2),
        border=False,
        position=(0, 0),
        velocity=(2, 1),
    )
    second = Panel(
        CallbackEffect(lambda b: b.clear_buffer(val="B")),
        size=(2, 2),
        border=False,
        position=(2, 1),
        velocity=(-1, 0),
    )
    scene = Scene(first, second)
    scene.start()
    try:
        for width, height in ((8, 5), (4, 3), (12, 8)):
            scene.resize((width, height))
            scene.update(1)
            frame = Buffer(height, width).clear_buffer(val=".")
            scene.draw(frame)
            expected = [["."] * width for _ in range(height)]
            for panel, glyph in ((first, "A"), (second, "B")):
                x, y = map(int, panel.position)
                for row in range(height):
                    for col in range(width):
                        if (
                            x <= col < x + panel.size[0]
                            and y <= row < y + panel.size[1]
                        ):
                            expected[row][col] = glyph
            assert frame.buffer == expected
    finally:
        scene.close()
