import pytest

from bruhanimate import Buffer, capture
from bruhanimate.demos.tv_demo import build_scene


def test_screen_cannot_paint_over_cabinet_or_background_and_draw_is_pure():
    scene = build_scene(Buffer(24, 80))
    scene.start()
    try:
        for _ in range(150):
            scene.update(1 / 60)
        background, cabinet, screen, badge, captions = scene.layers
        assert badge.animation.finished
        under = Buffer(24, 80)
        background.animation.draw(under)
        cabinet.animation.draw(under)
        captions.animation.draw(under)
        plasma = Buffer(24, 80)
        screen.animation.draw(plasma)
        first, second = Buffer(24, 80), Buffer(24, 80)
        scene.draw(first)
        scene.draw(second)
        assert first.buffer == second.buffer
        x, y, width, height = screen.region
        for row in range(24):
            for column in range(80):
                expected = (
                    plasma.buffer[row][column]
                    if x <= column < x + width and y <= row < y + height
                    else under.buffer[row][column]
                )
                assert first.buffer[row][column] == expected
        assert background.animation.buffer is not screen.animation.buffer
    finally:
        scene.close()


@pytest.mark.parametrize("size", [(80, 24), (40, 14), (5, 3), (1, 1)])
def test_tv_continues_animating_after_channel_badge_expires(size):
    frames = []
    assert (
        capture(
            effect_factory=build_scene,
            on_frame=frames.append,
            width=size[0],
            height=size[1],
            frames=151,
            fps=60,
            updates_per_second=60,
            on_complete="hold",
        )
        == 151
    )
    assert all(frame.width == size[0] and frame.height == size[1] for frame in frames)
    if size == (80, 24):
        assert "CH 01 / PLASMA" in frames[0].text()
        assert "CH 01 / PLASMA" not in frames[-1].text()
        assert frames[-1].cells != frames[-10].cells
        assert "CH 01 / PLASMA" in frames[0].text()  # Snapshots remain immutable.


def test_effects_advance_at_independent_rates_between_presentations():
    scene = build_scene(Buffer(24, 80))
    scene.start()
    try:
        snow = scene.layers[0].animation
        plasma = scene.layers[2].animation
        ticks = {"snow": [], "plasma": []}
        snow.update = ticks["snow"].append
        plasma.update = ticks["plasma"].append
        for _ in range(60):
            scene.update(1 / 60)
            scene.draw(Buffer(24, 80))
        assert ticks["snow"] == [1 / 15] * 15
        assert ticks["plasma"] == [1 / 30] * 30
    finally:
        scene.close()
