"""Deterministic viewport changes; no physical terminal or hardware claims."""

from unittest.mock import Mock

import pytest
from test_player import Clock, RecordingScreen, TrackingEffect

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Column,
    Fixed,
    Label,
    Layer,
    Panel,
    Playback,
    Player,
    Resizable,
    Row,
    Scene,
    Slot,
    StatusBar,
    TimedOverlay,
    effects,
    play,
)
from bruhanimate.demos.dashboard_demo import build_scene, draw_state, solve


class ResizingScreen(RecordingScreen):
    def __init__(self, changes, events=()):
        super().__init__(events)
        self.changes = dict(changes)
        self.refreshes = 0
        self.presentations = []

    def has_resized(self):
        return self.batches in self.changes

    def refresh_size(self):
        self.width, self.height = self.changes.pop(self.batches)
        self.refreshes += 1
        return True

    def flush_frame(self):
        self.presentations.append((self.width, self.height, list(self.writes)))
        self.writes.clear()
        super().flush_frame()


def test_player_repaints_grow_shrink_and_same_size_without_restarting():
    screen = ResizingScreen({1: (2, 1), 2: (8, 4), 3: (8, 4)})
    clock = Clock()
    effect = TrackingEffect(Buffer(3, 5))
    assert (
        Player(
            screen, effect, frames=4, on_resize="resize", clock=clock, sleep=clock.sleep
        ).run()
        == 4
    )
    assert effect.calls == ["start", 0, 1, 2, 3, "close"]
    assert effect.buffer.width() == 5 and effect.buffer.height() == 3
    for width, height, writes in screen.presentations:
        assert len(writes) == width * height  # Entire frame invalidated each time.
        assert {(x, y) for x, y, _ in writes} == {
            (x, y) for y in range(height) for x in range(width)
        }
    assert not screen.closed


def test_player_factory_only_called_once_and_duration_survives_resize():
    screen = ResizingScreen({1: (3, 2), 2: (4, 3)})
    clock = Clock()
    factory = Mock(side_effect=lambda b: TrackingEffect(b))
    assert (
        Player(
            screen,
            effect_factory=factory,
            fps=10,
            duration=0.3,
            on_resize="resize",
            clock=clock,
            sleep=clock.sleep,
        ).run()
        == 3
    )
    factory.assert_called_once()
    assert clock.now == pytest.approx(0.3)


def test_resize_failure_closes_owned_children_and_borrowed_content_stays_open():
    for owned in (True, False):
        screen = ResizingScreen({0: (8, 4)})
        effect = TrackingEffect(Buffer(3, 5))
        effect.resize = Mock(side_effect=RuntimeError("resize failed"))
        if not owned:
            effect.start()
        with pytest.raises(RuntimeError, match="resize failed"):
            Player(screen, effect, on_resize="resize", manage_effect=owned).run()
        assert effect.calls == (["start", "close"] if owned else ["start"])
        assert not screen.closed
        if not owned:
            effect.close()


def test_temporarily_empty_screen_does_not_spin_or_draw_and_honors_deadline():
    screen = ResizingScreen({0: (0, 0)})
    screen.refresh_size = Mock(return_value=False)
    clock = Clock()
    effect = TrackingEffect(Buffer(3, 5))
    assert (
        Player(
            screen,
            effect,
            on_resize="resize",
            duration=0.12,
            clock=clock,
            sleep=clock.sleep,
        ).run()
        == 0
    )
    assert effect.calls == ["start", "close"]
    assert clock.now == pytest.approx(0.15)
    assert not screen.writes


def test_empty_screen_still_accepts_quit():
    screen = ResizingScreen({0: (0, 0)}, events=[ord("q")])
    screen.refresh_size = Mock(return_value=False)
    assert Player(screen, CallbackEffect(lambda b: None), on_resize="resize").run() == 0


def test_resize_is_validated_before_opening_terminal(monkeypatch):
    show = Mock(side_effect=AssertionError("terminal opened"))
    monkeypatch.setattr("bruhanimate.player.Screen.show", show)
    with pytest.raises(ValueError, match="on_resize"):
        play("snow", on_resize="restart")
    with pytest.raises(ValueError, match="on_resize"):
        Player(RecordingScreen(), "snow", on_resize=None)
    show.assert_not_called()


def test_typed_effect_play_forwards_resize_policy(monkeypatch):
    run = Mock(return_value=5)
    monkeypatch.setattr("bruhanimate.player.play", run)
    assert effects.snow.play(on_resize="resize") == 5
    assert run.call_args.kwargs["on_resize"] == "resize"


def test_fixed_raster_survives_clipping_and_growth_without_mutating_frames():
    effect = TrackingEffect(Buffer(3, 5))
    effect.start()
    effect.update(0.1)
    original = Buffer(3, 5)
    effect.draw(original)
    snapshot = [row[:] for row in original.buffer]
    rng = effect.rng.getstate()
    effect.resize((1, 1))
    small = Buffer(1, 1)
    effect.draw(small)
    assert small.buffer == [["X"]]
    effect.resize((7, 4))
    large = Buffer(4, 7).clear_buffer(val=".")
    effect.draw(large)
    assert large.buffer[0] == list("X    ..")
    assert large.buffer[-1] == list(".......")
    assert original.buffer == snapshot and effect.tick == 1
    assert effect.rng.getstate() == rng
    effect.close()


def test_reflow_moves_slots_and_realigns_widgets_without_getter_calls():
    getter = Mock(return_value="title")
    layout = Column(
        Slot(Label(getter, align="center"), size=Fixed(1)),
        Slot(Row(Slot(Label("left")), Slot(Label("right", align="right")))),
        Slot(StatusBar("L", right="R"), size=Fixed(1)),
    ).build(Buffer(4, 12))
    assert isinstance(layout, Resizable)
    layout.start()
    layout.resize((20, 5))
    target = Buffer(5, 20)
    layout.draw(target)
    assert "".join(target.buffer[0]) == "       title        "
    assert "".join(target.buffer[1]) == "left           right"
    assert "".join(target.buffer[-1]) == "L                  R"
    getter.assert_called_once()
    layout.close()


def test_hidden_factory_starts_once_on_first_visible_allocation():
    effect = TrackingEffect(Buffer(2, 3))
    factory = Mock(return_value=effect)
    layout = Row(
        Slot(Label("fixed"), size=Fixed(4)), Slot(effect_factory=factory)
    ).build(Buffer(2, 2))
    layout.start()
    factory.assert_not_called()
    layout.resize((7, 2))
    layout.update(0.1)
    layout.resize((2, 1))
    layout.update(0.1)
    layout.resize((8, 3))
    layout.draw(Buffer(3, 8))
    factory.assert_called_once()
    layout.close()
    layout.close()
    assert effect.calls == ["start", 0, 1, "close"]


def test_reflow_failure_still_releases_late_factory_and_earlier_children():
    earlier = TrackingEffect(Buffer(2, 4))
    late = TrackingEffect(Buffer(2, 3), failure="start")
    layout = Row(
        Slot(earlier, size=Fixed(4)), Slot(effect_factory=lambda b: late)
    ).build(Buffer(2, 4))
    layout.start()
    try:
        with pytest.raises(RuntimeError, match="start failed"):
            layout.resize((7, 2))
    finally:
        layout.close()
    assert earlier.calls == ["start", "close"]
    assert late.calls == ["start", "close"]


def test_panel_fit_keeps_layer_clock_and_fixed_panel_geometry():
    effect = TrackingEffect(Buffer(2, 3))
    panel = Panel(effect, size=(3, 2), fit=True, updates_per_second=2)
    fixed = Panel(Label("fixed"), size=(3, 2))
    scene = Scene(panel, fixed)
    scene.start()
    scene.update(0.25)
    scene.resize((12, 7))
    assert panel.size == (10, 5) and fixed.size == (3, 2)
    assert effect.tick == 0
    scene.update(0.25)
    assert effect.tick == 1
    scene.draw(Buffer(7, 12))
    scene.close()


def test_scene_layer_and_overlay_clocks_survive_resize():
    effect = TrackingEffect(Buffer(3, 5))
    overlay = TimedOverlay(effect, duration=1, delay=0.5)
    scene = Scene(Layer(overlay, updates_per_second=4))
    scene.start()
    scene.update(0.125)
    scene.resize((2, 1))
    scene.update(0.375)
    scene.draw(Buffer(1, 2))
    assert effect.calls == ["start"]  # Activation at the delay boundary.
    scene.update(1)
    assert overlay.finished
    scene.resize((8, 4))  # An expired child's resources stay closed.
    scene.close()
    assert effect.calls.count("close") == 1


@pytest.mark.parametrize("size", [(0, 3), (3, -1), (True, 2), (2.5, 3), [2, 3]])
def test_resize_dimensions_are_validated(size):
    with pytest.raises((TypeError, ValueError)):
        TrackingEffect(Buffer(3, 5)).resize(size)
    with pytest.raises((TypeError, ValueError)):
        Panel(Label("x"), size=(2, 1), fit=True).resize(size)


def test_dashboard_preserves_solver_snapshot_speed_pending_step_and_iterator():
    class Source:
        def __init__(self):
            self.iterator = iter(solve())
            self.acquired = self.consumed = self.closed = 0

        def __iter__(self):
            self.acquired += 1
            return self

        def __next__(self):
            self.consumed += 1
            return next(self.iterator)

        def close(self):
            self.closed += 1
            self.iterator.close()

    source = Source()
    playback = Playback(source, draw_state, steps_per_second=2)
    scene = build_scene(Buffer(24, 80), playback)
    scene.start()
    scene.update(1 / 60)
    playback.pause()
    playback.steps_per_second = 7
    playback.step()
    state = playback.state
    for size in ((40, 14), (1, 1), (100, 30), (80, 24)):
        scene.resize(size)
        target = Buffer(size[1], size[0])
        scene.draw(target)
        assert playback.state is state and playback.steps == 1
        assert playback.paused and playback.steps_per_second == 7
        assert source.acquired == source.consumed == 1 and source.closed == 0
    scene.update(1 / 60)
    assert playback.steps == 2 and playback.paused
    scene.resize((1, 1))
    playback.step()
    scene.update(1 / 60)
    assert playback.steps == 3  # Existing children continue while hidden.
    scene.resize((80, 24))
    scene.draw(Buffer(24, 80))
    scene.close()
    scene.close()
    assert source.acquired == source.closed == 1


def test_dashboard_initially_tiny_can_grow_and_start_solver():
    playback = Playback(solve(), draw_state)
    scene = build_scene(Buffer(1, 1), playback)
    scene.start()
    scene.resize((80, 24))
    scene.update(1 / 60)
    scene.draw(Buffer(24, 80))
    assert playback.steps == 1
    scene.close()


def test_supplied_content_can_reflow_before_start_without_factory_or_restart():
    effect = TrackingEffect(Buffer(3, 5))
    panel = Panel(effect, size=(5, 3), fit=True)
    layout = Row(Slot(panel)).build(Buffer(5, 7))
    layout.resize((12, 8))
    assert effect.calls == []
    layout.start()
    assert panel.outer_size == (12, 8)
    layout.draw(Buffer(8, 12))
    layout.close()
    assert effect.calls == ["start", "close"]
