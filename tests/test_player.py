from collections import deque
from unittest.mock import Mock

import pytest

from bruhanimate import (
    Animation,
    BaseEffect,
    Buffer,
    CallbackEffect,
    FramePresenter,
    Player,
    Screen,
    play,
)
from bruhanimate.bruhutil.bruherrors import ScreenResizedError


class RecordingScreen:
    height = 3
    width = 5

    def __init__(self, events=()):
        self.events = deque(events)
        self.writes = []
        self.batches = 0
        self.resized = False
        self.closed = False

    def get_event(self):
        return self.events.popleft() if self.events else None

    def has_resized(self):
        return self.resized

    def begin_frame(self):
        pass

    def flush_frame(self):
        self.batches += 1

    def print_at(self, text, x, y, width):
        self.writes.append((x, y, text))

    def close(self):
        self.closed = True


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.now += seconds


class TrackingEffect(BaseEffect):
    def __init__(self, buffer, background=" ", failure=None):
        super().__init__(buffer, background)
        self.failure = failure
        self.calls = []
        self.tick = 0

    def start(self):
        self.calls.append("start")
        super().start()
        if self.failure == "start":
            raise RuntimeError("start failed")

    def update(self, dt):
        frame_number = self.tick
        self.tick += 1
        self.calls.append(frame_number)
        if self.failure == "render":
            raise RuntimeError("render failed")
        if self.failure == "interrupt":
            raise KeyboardInterrupt
        self.buffer.put_char(frame_number % self.buffer.width(), 0, "X")

    def close(self):
        self.calls.append("close")
        super().close()


def test_native_effect_retains_trails_and_drawing_does_not_advance():
    effect = TrackingEffect(Buffer(3, 5))
    effect.start()
    try:
        effect.update(0.1)
        effect.update(0.1)
        first, second = Buffer(3, 5), Buffer(3, 5)
        effect.draw(first)
        effect.draw(second)

        assert effect.calls == ["start", 0, 1]
        assert first.buffer == second.buffer
        assert first.buffer[0] == ["X", "X", " ", " ", " "]
    finally:
        effect.close()


def test_factory_receives_sized_buffer_and_is_not_called_during_construction():
    screen = RecordingScreen()
    created = []

    def factory(buffer):
        assert (buffer.height(), buffer.width()) == (3, 5)
        effect = TrackingEffect(buffer)
        created.append(effect)
        return effect

    player = Player(screen, effect_factory=factory, frames=3, fps=None)
    assert not created

    assert player.run() == 3
    assert created[0].calls == ["start", 0, 1, 2, "close"]
    assert not screen.closed


def test_callback_drawing_restores_previous_pixels_and_avoids_redundant_writes():
    screen = RecordingScreen()
    count = 0

    def draw(buffer):
        nonlocal count
        if count < 2:
            buffer.put_char(0, 0, "X")
        count += 1

    Player(screen, CallbackEffect(draw), frames=3, fps=None).run()

    # First paint includes the full screen; the unchanged second frame writes
    # nothing, and the third clears the now-absent X.
    assert len(screen.writes) == 16
    assert screen.writes[-1] == (0, 0, " ")
    assert screen.batches == 3


@pytest.mark.parametrize("fps", [30, 60])
def test_fixed_ticks_are_independent_of_presentation_rate(fps):
    clock = Clock()
    deltas = []
    animation = CallbackEffect(lambda buffer: None, update=deltas.append)

    frames = Player(
        RecordingScreen(),
        animation,
        fps=fps,
        updates_per_second=10,
        frames=fps,
        clock=clock,
        sleep=clock.sleep,
    ).run()

    assert frames == fps
    assert deltas == [0.1] * 10


def test_stalls_bound_catch_up_work():
    clock = Clock()
    updates = []
    draws = 0

    def draw(buffer):
        nonlocal draws
        draws += 1
        if draws == 1:
            clock.now += 100

    Player(
        RecordingScreen(),
        CallbackEffect(draw, update=updates.append),
        fps=None,
        updates_per_second=10,
        frames=2,
        max_catch_up=3,
        clock=clock,
    ).run()

    assert len(updates) == 4  # initial tick, then at most three catch-up ticks


def test_uncapped_native_updates_receive_elapsed_time():
    clock = Clock()
    deltas = []

    def draw(buffer):
        clock.now += 0.1

    Player(
        RecordingScreen(),
        CallbackEffect(draw, update=deltas.append),
        fps=None,
        frames=3,
        clock=clock,
    ).run()
    assert deltas == pytest.approx([0, 0.1, 0.1])


def test_native_effect_advances_only_on_scheduled_ticks():
    clock = Clock()
    effect = TrackingEffect(Buffer(3, 5))
    Player(
        RecordingScreen(),
        effect,
        fps=60,
        updates_per_second=10,
        frames=60,
        clock=clock,
        sleep=clock.sleep,
    ).run()
    assert effect.calls == ["start", *range(10), "close"]


@pytest.mark.parametrize("failure", ["start", "render"])
def test_player_closes_on_startup_and_update_failure(failure):
    effect = TrackingEffect(Buffer(3, 5), failure=failure)

    with pytest.raises(RuntimeError, match=f"{failure} failed"):
        Player(RecordingScreen(), effect, frames=1, fps=None).run()

    assert effect.calls[-1] == "close"
    assert effect.calls.count("close") == 1


def test_player_closes_on_draw_failure():
    animation = Mock(spec=Animation)
    animation.draw.side_effect = ValueError("bad draw")
    with pytest.raises(ValueError, match="bad draw"):
        Player(RecordingScreen(), animation, frames=1, fps=None).run()
    animation.close.assert_called_once()


@pytest.mark.parametrize("reason", ["resize", "quit", "interrupt"])
def test_player_closes_on_every_exit_path(reason):
    screen = RecordingScreen(events=[ord("q")] if reason == "quit" else [])
    screen.resized = reason == "resize"
    effect = TrackingEffect(Buffer(3, 5), failure=reason)
    player = Player(screen, effect, frames=3, fps=None)

    if reason == "resize":
        with pytest.raises(ScreenResizedError):
            player.run()
    else:
        assert player.run() == 0
    assert effect.calls[-1] == "close"


def test_borrowed_effect_is_neither_started_nor_closed():
    effect = TrackingEffect(Buffer(3, 5))
    Player(RecordingScreen(), effect, frames=1, fps=None, manage_effect=False).run()
    assert effect.calls == [0]


def test_zero_frames_does_not_construct_or_start_content():
    factory = Mock()
    assert Player(RecordingScreen(), effect_factory=factory, frames=0).run() == 0
    factory.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"fps": 0},
        {"fps": float("nan")},
        {"fps": float("inf")},
        {"updates_per_second": -1},
        {"frames": -1},
        {"max_catch_up": 0},
        {"settings": object()},
        {"preset": "unused"},
    ],
)
def test_invalid_playback_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        Player(RecordingScreen(), CallbackEffect(lambda buffer: None), **options)


def test_factory_and_effect_are_unambiguous():
    with pytest.raises(ValueError, match="exactly one"):
        Player(RecordingScreen(), "snow", effect_factory=lambda buffer: None)
    with pytest.raises(TypeError, match="CallbackEffect"):
        Player(RecordingScreen(), lambda buffer: None, frames=1).run()


def test_frame_presenter_flushes_if_a_write_fails():
    screen = RecordingScreen()
    screen.print_at = Mock(side_effect=ValueError("write failed"))
    presenter = FramePresenter(screen)
    with pytest.raises(ValueError, match="write failed"):
        presenter.present(Buffer(3, 5))
    assert screen.batches == 1
    assert presenter.last_displayed.get_char(0, 0) is None


def test_play_restores_owned_screen_even_after_factory_failure(monkeypatch):
    screen = RecordingScreen()
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))

    def factory(buffer):
        raise ValueError("factory failed")

    with pytest.raises(ValueError, match="factory failed"):
        play(effect_factory=factory, frames=1)
    assert screen.closed


def test_named_effect_uses_the_registry():
    screen = RecordingScreen()
    assert Player(screen, "snow", preset="light", frames=1, fps=None).run() == 1


def test_player_accepts_a_custom_registered_native_effect(monkeypatch):
    from bruhanimate import effect_registry
    from bruhanimate.bruheffect.registry import EffectEntry

    created = []

    class CustomEffect(TrackingEffect):
        def __init__(self, buffer, background):
            super().__init__(buffer, background)
            created.append(self)

    monkeypatch.setitem(
        effect_registry._registry,
        "custom_test",
        EffectEntry("custom_test", CustomEffect, None, "Test"),
    )
    Player(RecordingScreen(), "custom_test", frames=2, fps=None).run()
    assert created[0].calls == ["start", 0, 1, "close"]
