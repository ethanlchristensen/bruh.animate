import re

import pytest

from bruhanimate import AudioEffect, BaseEffect, Buffer, Panel, capture
from bruhanimate.demos.windows_demo import build_scene


@pytest.fixture(autouse=True)
def no_audio_hardware(monkeypatch):
    monkeypatch.setattr(AudioEffect, "start", BaseEffect.start)


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
        # Larger front windows can cover some rear-window titles.
        assert all(name in initial for name in ("PLASMA", "FIRE", "AUDIO MIRROR"))
        assert frames[0].cells != frames[-1].cells
        assert frames[0].cells[0] == frames[-1].cells[0]
        assert frames[0].cells[-1] == frames[-1].cells[-1]


def test_scene_owns_five_distinct_local_effect_buffers():
    scene = build_scene(Buffer(24, 80))
    windows = [layer.animation for layer in scene.layers[1:-1]]
    assert all(isinstance(moving, Panel) for moving in windows)
    effects = [moving.animation for moving in windows]
    assert len({type(effect) for effect in effects}) == 5
    assert len({id(effect.buffer) for effect in effects}) == 5
    assert all(
        effect.buffer.width() < 80 and effect.buffer.height() < 24 for effect in effects
    )
    assert all(not effect._started for effect in effects)
    assert effects[-1].mode == "mirror"
    scene.close()


@pytest.mark.parametrize(
    "viewport,outer", [((80, 24), (36, 11)), ((160, 48), (60, 20))]
)
def test_larger_window_geometry_fits_local_effect_buffers(viewport, outer):
    scene = build_scene(Buffer(viewport[1], viewport[0]))
    try:
        for layer in scene.layers[1:-1]:
            panel = layer.animation
            assert panel.outer_size == outer
            assert panel.size == (outer[0] - 2, outer[1] - 2)
            assert (
                panel.animation.buffer.width(),
                panel.animation.buffer.height(),
            ) == panel.size
    finally:
        scene.close()


def test_audio_window_updates_moves_and_closes_with_scene(monkeypatch):
    from unittest.mock import Mock

    import numpy as np

    scene = build_scene(Buffer(24, 80), audio_mode="mirror")
    panel = scene.layers[-2].animation
    audio = panel.animation
    assert isinstance(audio, AudioEffect) and audio.mode == "mirror"
    assert panel.size == (audio.buffer.width(), audio.buffer.height())
    audio._audio_chunk = 0.2 * np.sin(2 * np.pi * 1000 * np.arange(1024) / 44100)
    update = Mock(wraps=audio.update)
    close = Mock(wraps=audio.close)
    monkeypatch.setattr(audio, "update", update)
    monkeypatch.setattr(audio, "close", close)
    initial_position = panel.position
    scene.start()
    try:
        for _ in range(12):
            scene.update(1 / 60)
        assert update.call_count == 6
        assert all(call.args == (1 / 30,) for call in update.call_args_list)
        assert panel.position != initial_position
        assert audio._bars.max() > 0
        assert any(cell != " " for row in audio.buffer.buffer for cell in row)
        first, second = Buffer(24, 80), Buffer(24, 80)
        scene.draw(first)
        scene.draw(second)
        assert first.buffer == second.buffer
        assert update.call_count == 6
    finally:
        scene.close()
        scene.close()
    close.assert_called_once()
    assert not audio._started


def test_audio_can_be_omitted_without_construction_or_capture(monkeypatch):
    import bruhanimate.demos.windows_demo as demo

    monkeypatch.setattr(
        demo, "AudioEffect", lambda *a, **kw: pytest.fail("audio constructed")
    )
    scene = build_scene(Buffer(24, 80), audio_mode=None)
    assert len(scene.layers[1:-1]) == 4
    scene.start()
    try:
        scene.update(1 / 60)
        frame = Buffer(24, 80)
        scene.draw(frame)
        assert "FOUR WINDOWS" in "".join(frame.buffer[0])
    finally:
        scene.close()


def test_failed_audio_start_closes_previously_started_windows(monkeypatch):
    def fail(effect):
        raise RuntimeError("capture startup failed")

    monkeypatch.setattr(AudioEffect, "start", fail)
    scene = build_scene(Buffer(24, 80))
    with pytest.raises(RuntimeError, match="capture startup failed"):
        scene.start()
    assert all(not layer.animation.animation._started for layer in scene.layers[1:-1])
    scene.close()


def test_capture_error_appears_in_full_width_footer():
    scene = build_scene(Buffer(24, 80))
    scene.start()
    try:
        audio = scene.layers[-2].animation.animation
        audio._error = (
            "Audio error: install bruhanimate[audio] to enable system capture"
        )
        frame = Buffer(24, 80)
        scene.draw(frame)
        assert audio._error in "".join(frame.buffer[-1])
    finally:
        scene.close()
