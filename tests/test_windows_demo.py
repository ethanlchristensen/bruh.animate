import re

import pytest

from bruhanimate import Buffer, Panel, capture
from bruhanimate.demos.windows_demo import build_scene


@pytest.mark.parametrize("size", [(80, 24), (40, 14), (5, 3), (1, 1)])
def test_complete_demo_is_clipped_and_renders_valid_cells_without_a_terminal(size):
    frames = []
    assert (
        capture(
            effect_factory=build_scene,
            on_frame=frames.append,
            width=size[0],
            height=size[1],
            frames=91,
            fps=30,
            updates_per_second=60,
        )
        == 91
    )
    for frame in frames:
        assert len(frame.cells) == size[1]
        for row in frame.cells:
            assert len(row) == size[0]
            for cell in row:
                glyph = re.sub(r"\x1b\[[0-9;]*m", "", cell)
                assert len(glyph) == 1 and "\x1b" not in glyph
    if size == (80, 24):
        initial = re.sub(r"\x1b\[[0-9;]*m", "", frames[0].text())
        assert all(name in initial for name in ("PLASMA", "FIRE", "SNOW", "MATRIX"))
        assert frames[0].cells != frames[-1].cells
        assert frames[0].cells[0] == frames[-1].cells[0]
        assert frames[0].cells[-1] == frames[-1].cells[-1]


def test_scene_owns_four_distinct_local_effect_buffers():
    scene = build_scene(Buffer(24, 80))
    windows = [layer.animation for layer in scene.layers[1:-1]]
    assert all(isinstance(moving, Panel) for moving in windows)
    effects = [moving.animation for moving in windows]
    assert len({type(effect) for effect in effects}) == 4
    assert len({id(effect.buffer) for effect in effects}) == 4
    assert all(
        effect.buffer.width() < 80 and effect.buffer.height() < 24 for effect in effects
    )
    assert all(not effect._started for effect in effects)
    scene.close()
