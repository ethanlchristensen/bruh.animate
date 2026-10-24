import re

import pytest

from bruhanimate import Buffer, capture, get_image
from bruhanimate.demos.tv_demo import COMPUTER, SCREEN_SPANS, _origin, build_scene


def test_screen_cannot_paint_over_cabinet_or_background_and_draw_is_pure():
    scene = build_scene(Buffer(24, 80))
    scene.start()
    try:
        for _ in range(150):
            scene.update(1 / 60)
        background, cabinet, screen, title, badge, captions = scene.layers
        assert badge.animation.finished
        under = Buffer(24, 80)
        background.animation.draw(under)
        cabinet.animation.draw(under)
        captions.animation.draw(under)
        plasma = Buffer(24, 80)
        screen.animation.draw(plasma)
        lettering = Buffer(24, 80).clear_buffer(val=None)
        title.animation.draw(lettering)
        for row in range(24):
            for column in range(80):
                glyph = lettering.get_char(column, row)
                if glyph is not None:
                    base = plasma.get_char(column, row)
                    plasma.put_char(
                        column, row, base.replace(" ", f"\x1b[1;38;5;231m{glyph}", 1)
                    )
        first, second = Buffer(24, 80), Buffer(24, 80)
        scene.draw(first)
        scene.draw(second)
        assert first.buffer == second.buffer
        x, y = _origin(first)
        opening = {
            (x + col, y + row)
            for row, start, stop in SCREEN_SPANS
            for col in range(start, stop)
            if 1 <= y + row < 23
        }
        for row in range(24):
            for column in range(80):
                expected = (
                    plasma.buffer[row][column]
                    if (column, row) in opening
                    else under.buffer[row][column]
                )
                assert first.buffer[row][column] == expected
        assert background.animation.buffer is not screen.animation.buffer
    finally:
        scene.close()


def test_original_computer_art_is_preserved_and_only_blanks_form_the_screen():
    original = tuple(get_image("computer"))
    assert COMPUTER == tuple(row.rstrip() for row in original)
    assert all(COMPUTER[row][45:] == "|||" for row in range(3, 12))
    for row, start, stop in SCREEN_SPANS:
        assert COMPUTER[row][start:stop] == " " * (stop - start)
    scene = build_scene(Buffer(34, 80))
    scene.start()
    try:
        scene.update(3)
        frame = Buffer(34, 80)
        scene.draw(frame)
        left, top = _origin(frame)
        for y, row in enumerate(COMPUTER):
            for x, char in enumerate(row):
                if char != " ":
                    assert f"m{char}\x1b[0m" in frame.get_char(left + x, top + y)
        assert tuple(get_image("computer")) == original
    finally:
        scene.close()


def test_resize_recenters_computer_and_keeps_badge_expired_and_clocks_live():
    scene = build_scene(Buffer(34, 80))
    scene.start()
    try:
        for _ in range(150):
            scene.update(1 / 60)
        plasma = scene.layers[2].animation
        phase = plasma.t
        for width, height in ((110, 40), (5, 3), (1, 1), (80, 34)):
            scene.resize((width, height))
            frame = Buffer(height, width)
            scene.draw(frame)
            assert scene.layers[4].animation.finished
            assert plasma.t == phase
            if width >= 80:
                left, top = _origin(frame)
                assert f"m{COMPUTER[0][23]}\x1b[0m" in frame.get_char(left + 23, top)
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
        assert "CH 01 / PLASMA" in re.sub(r"\x1b\[[0-9;]*m", "", frames[0].text())
        assert "CH 01 / PLASMA" not in re.sub(r"\x1b\[[0-9;]*m", "", frames[-1].text())
        assert frames[-1].cells != frames[-10].cells
        assert "CH 01 / PLASMA" in re.sub(
            r"\x1b\[[0-9;]*m", "", frames[0].text()
        )  # Snapshots remain immutable.


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


def test_figlet_reveal_keeps_live_plasma_color_and_resize_progress():
    scene = build_scene(Buffer(34, 80))
    scene.start()
    try:
        plasma = scene.layers[2].animation
        title = scene.layers[3].animation
        scene.update(2)
        before = Buffer(34, 80)
        before.clear_buffer(val=None)
        title.draw(before)
        assert all(cell is None for row in before.buffer for cell in row)
        scene.update(0.7)
        first = Buffer(34, 80)
        first.clear_buffer(val=None)
        title.draw(first)
        first_count = sum(cell is not None for row in first.buffer for cell in row)
        assert first_count > 0
        assert not title.finished
        for _ in range(240):
            scene.update(1 / 60)
        assert not title.finished  # The completed lettering holds, then repeats.
        phase = plasma.t
        for width, height in ((110, 40), (1, 1), (80, 34)):
            scene.resize((width, height))
            frame = Buffer(height, width)
            scene.draw(frame)
            assert not title.finished
            assert plasma.t == phase
            if width >= 80:
                left, top = _origin(frame)
                for row, text in enumerate(title.rows):
                    for column, glyph in enumerate(text):
                        if glyph == " ":
                            continue
                        x, y = left + 23 + column, top + 6 + row
                        assert any(
                            r == 6 + row and a <= 23 + column < b
                            for r, a, b in SCREEN_SPANS
                        )
                        base = plasma.buffer.get_char(x, y)
                        assert frame.get_char(x, y) == base.replace(
                            " ", f"\x1b[1;38;5;231m{glyph}", 1
                        )
        assert (
            sum(cell is not None for row in first.buffer for cell in row) == first_count
        )
    finally:
        scene.close()


def test_title_repeats_without_restarting_plasma_or_channel_badge():
    scene = build_scene(Buffer(34, 80))
    scene.start()
    try:
        plasma = scene.layers[2].animation
        title = scene.layers[3].animation
        flight = sum(char != " " for row in title.rows for char in row) / 18 + 0.65

        def advance(seconds):
            while seconds > 1 / 60:
                scene.update(1 / 60)
                seconds -= 1 / 60
            scene.update(seconds)

        advance(2 + 2 * flight + 3)
        blank = Buffer(34, 80)
        blank.clear_buffer(val=None)
        title.draw(blank)
        assert all(cell is None for row in blank.buffer for cell in row)
        phase = plasma.t
        first = Buffer(34, 80)
        scene.draw(first)
        advance(0.5)
        second = Buffer(34, 80)
        scene.draw(second)
        assert plasma.t > phase
        assert first.buffer != second.buffer
        left, top = _origin(second)
        for row, start, stop in SCREEN_SPANS:
            for column in range(start, stop):
                x, y = left + column, top + row
                assert second.get_char(x, y) == plasma.buffer.get_char(x, y)
        advance(0.5 + flight)
        visible = Buffer(34, 80)
        visible.clear_buffer(val=None)
        title.draw(visible)
        assert any(cell is not None for row in visible.buffer for cell in row)
        assert scene.layers[4].animation.finished
        assert not title.finished
        assert not scene.finished
    finally:
        scene.close()


def test_all_tv_entrances_stay_inside_mask_and_preserve_phase_during_resize():
    scene = build_scene(Buffer(34, 80))
    scene.start()
    try:
        title = scene.layers[3].animation
        scene.update(2)
        seen = set()
        for _ in range(36 * 30):
            scene.update(1 / 30)
            seen.add(title.phase_name)
            under = Buffer(34, 80)
            scene.layers[0].animation.draw(under)
            scene.layers[1].animation.draw(under)
            scene.layers[5].animation.draw(under)
            frame = Buffer(34, 80)
            scene.draw(frame)
            for y in range(34):
                for x in range(80):
                    if not scene.layers[2].mask(x, y, (80, 34)):
                        assert frame.get_char(x, y) == under.get_char(x, y)
            before = title.current
            title_frame = Buffer(34, 80).clear_buffer(val=None)
            title.draw(title_frame)
            scene.resize((1, 1))
            scene.draw(Buffer(1, 1))
            scene.resize((80, 34))
            assert title.current is before
            again = Buffer(34, 80).clear_buffer(val=None)
            title.draw(again)
            assert again.buffer == title_frame.buffer
        assert seen == {"Glitch", "Focus", "Dissolve", "Wipe"}
    finally:
        scene.close()
