from unittest.mock import Mock

import pytest
from test_player import Clock, RecordingScreen, TrackingEffect

from bruhanimate import (
    Animation,
    BaseEffect,
    Buffer,
    CallbackEffect,
    ImageEffect,
    Layer,
    Player,
    Scene,
)
from bruhanimate.demos._showcase import Showcase


def paint(text):
    return CallbackEffect(lambda buffer: buffer.put_at(0, 0, text))


def test_layers_are_isolated_and_transparency_is_explicit():
    scene = Scene(paint("ABCDE"), Layer(paint(" X Y "), transparent=True))
    first, second = Buffer(3, 5), Buffer(3, 5)
    scene.draw(first)
    scene.draw(second)
    assert first.buffer == second.buffer
    assert first.buffer[0] == list("AXCYE")

    opaque = Buffer(3, 5)
    Scene(paint("ABCDE"), paint(" X Y ")).draw(opaque)
    assert opaque.buffer[0] == list(" X Y ")


def test_centered_image_presents_through_player_without_redundant_writes():
    screen, clock = RecordingScreen(), Clock()
    player = Player(
        screen,
        Scene(ImageEffect("X")),
        frames=3,
        fps=30,
        clock=clock,
        sleep=clock.sleep,
    )
    player.run()
    assert player.presenter.last_displayed.get_char(2, 1) == "X"
    assert len(screen.writes) == 15


def test_moving_overlay_reveals_current_lower_layer():
    position = {"text": "ABCDE"}
    background = CallbackEffect(lambda buffer: buffer.put_at(0, 0, position["text"]))
    overlay = ImageEffect("X", x=0, y=0, velocity=(1, 0))
    scene = Scene(background, overlay)
    first, second = Buffer(1, 5), Buffer(1, 5)
    scene.draw(first)
    position["text"] = "12345"
    scene.update(1)
    scene.draw(second)
    assert first.buffer == [list("XBCDE")]
    assert second.buffer == [list("1X345")]


def test_moving_image_advances_in_seconds_and_clips_at_edges():
    image = ImageEffect("ABCDE", x=-2, y=0, velocity=(2, 0))
    first, second = Buffer(1, 3), Buffer(1, 3)
    image.draw(first)
    image.draw(second)
    assert first.buffer == second.buffer == [list("CDE")]
    image.update(0.5)
    image.draw(second)
    assert second.buffer == [list("BCD")]


def test_scene_starts_once_and_closes_children_in_reverse_order():
    calls = []
    children = []
    for label in ("first", "second"):
        child = Mock(spec=Animation)
        child.start.side_effect = lambda label=label: calls.append(f"start {label}")
        child.close.side_effect = lambda label=label: calls.append(f"close {label}")
        children.append(child)
    scene = Scene(*children)
    scene.start()
    scene.start()
    scene.close()
    scene.close()
    assert calls == ["start first", "start second", "close second", "close first"]


def test_partial_scene_startup_cleans_started_and_failing_children():
    first = TrackingEffect(Buffer(3, 5))
    failing = TrackingEffect(Buffer(3, 5), failure="start")
    unstarted = TrackingEffect(Buffer(3, 5))
    with pytest.raises(RuntimeError, match="start failed"):
        Player(RecordingScreen(), Scene(first, failing, unstarted), frames=1).run()
    assert first.calls == ["start", "close"]
    assert failing.calls == ["start", "close"]
    assert unstarted.calls == []


def test_scene_rejects_duplicate_ownership_and_invalid_children():
    child = ImageEffect("X")
    with pytest.raises(ValueError, match="same animation twice"):
        Scene(child, child)
    with pytest.raises(TypeError, match="Animation"):
        Scene(lambda: None)


def test_showcase_switches_effects_with_owned_cleanup():
    first, second = TrackingEffect(Buffer(3, 5)), TrackingEffect(Buffer(3, 5))
    showcase = Showcase([("one", first), ("two", second)], duration=0.1, title="Test")
    clock = Clock()
    Player(
        RecordingScreen(), showcase, frames=6, fps=30, clock=clock, sleep=clock.sleep
    ).run()
    assert first.calls == second.calls == ["start", 0, 1, 2, "close"]


def test_effect_draw_snapshots_mutable_cells_and_preserves_transparency():
    class Cell:
        text = "A"

        def __str__(self):
            return self.text

    effect = TrackingEffect(Buffer(1, 2))
    cell = Cell()
    effect.buffer.put_char(0, 0, cell)
    effect.buffer.put_char(1, 0, None)
    first, second = Buffer(1, 2), Buffer(1, 2)
    first.clear_buffer(val=".")
    effect.draw(first)
    cell.text = "B"
    effect.draw(second)
    assert first.buffer == [["A", "."]]
    assert second.buffer == [["B", " "]]


def test_base_effect_requires_native_update():
    with pytest.raises(TypeError, match="abstract"):
        BaseEffect(Buffer(1, 1), " ")
