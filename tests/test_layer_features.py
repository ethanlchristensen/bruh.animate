import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import (
    Buffer,
    CallbackEffect,
    ImageEffect,
    Layer,
    Playback,
    Player,
    Scene,
    TimedOverlay,
)


class Probe:
    def __init__(self, label="x", events=None, failure=None):
        self.label = label
        self.events = events if events is not None else []
        self.failure = failure
        self.updates = []
        self.draws = 0

    def start(self):
        self.events.append(f"start {self.label}")
        if self.failure == "start":
            raise RuntimeError("start failed")

    def update(self, dt):
        self.updates.append(dt)
        if self.failure == "update":
            raise RuntimeError("update failed")

    def draw(self, buffer):
        self.draws += 1
        buffer.clear_buffer(val=self.label)

    def close(self):
        self.events.append(f"close {self.label}")


@pytest.mark.parametrize(
    "region, expected",
    [
        ((1, 1, 2, 1), ["....", ".xx.", "...."]),
        ((-1, -1, 3, 3), ["xx..", "xx..", "...."]),
        ((3, 2, 9, 9), ["....", "....", "...x"]),
        ((0, 0, 0, 3), ["...."] * 3),
        ((9, 9, 2, 2), ["...."] * 3),
    ],
)
def test_region_clips_destination_without_resizing_child_buffer(region, expected):
    sizes = []

    def draw(buffer):
        sizes.append((buffer.width(), buffer.height()))
        buffer.clear_buffer(val="x")

    scene = Scene(Layer(CallbackEffect(draw), region=region))
    buffer = Buffer(3, 4).clear_buffer(val=".")
    scene.draw(buffer)
    assert ["".join(row) for row in buffer.buffer] == expected
    assert all(size == (4, 3) for size in sizes)


def test_region_does_not_translate_and_preserves_none_spaces_and_sgr():
    def overlay(buffer):
        for x, value in enumerate(["!", None, " ", "\x1b[41m \x1b[0m", "x"]):
            buffer.put_char(x, 0, value)

    scene = Scene(
        ImageEffect("ABCDE", x=0, y=0),
        Layer(CallbackEffect(overlay), transparent=True, region=(1, 0, 3, 1)),
    )
    buffer = Buffer(1, 5)
    scene.draw(buffer)
    assert buffer.buffer == [["A", "B", "C", "\x1b[41m \x1b[0m", "E"]]


@pytest.mark.parametrize("fps", [30, 60, 120])
def test_layer_rates_are_independent_of_presentation(fps):
    slow, fast, inherited = Probe(), Probe(), Probe()
    scene = Scene(
        Layer(slow, updates_per_second=5), Layer(fast, updates_per_second=15), inherited
    )
    for _ in range(fps):
        scene.update(1 / fps)
        scene.draw(Buffer(1, 1))
    assert slow.updates == [0.2] * 5
    assert fast.updates == [1 / 15] * 15
    assert inherited.updates == [1 / fps] * fps
    assert slow.draws == fast.draws == inherited.draws == fps


def test_fixed_clock_waits_for_interval_and_preserves_fractional_time():
    child = Probe()
    scene = Scene(Layer(child, updates_per_second=4))
    for dt in (0, 0.1, 0.1):
        scene.update(dt)
    assert not child.updates
    scene.update(0.1)
    assert child.updates == [0.25]
    scene.update(0.2)
    assert child.updates == [0.25, 0.25]
    scene.draw(Buffer(1, 1))
    scene.draw(Buffer(1, 1))
    assert len(child.updates) == 2


def test_catchup_is_bounded_and_offscreen_layers_still_update():
    child = Probe()
    scene = Scene(
        Layer(child, region=(0, 0, 0, 0), updates_per_second=10, max_catch_up=2)
    )
    scene.update(100)
    scene.draw(Buffer(1, 1))
    assert child.updates == [0.1, 0.1] and child.draws == 0
    scene.update(0)
    assert len(child.updates) == 2
    scene.update(0.1)
    assert len(child.updates) == 3


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"region": [0, 0, 1, 1]}, TypeError),
        ({"region": (0, 0, 1)}, TypeError),
        ({"region": (0, 0, -1, 1)}, ValueError),
        ({"region": (True, 0, 1, 1)}, TypeError),
        ({"updates_per_second": 0}, ValueError),
        ({"updates_per_second": -1}, ValueError),
        ({"updates_per_second": float("inf")}, ValueError),
        ({"updates_per_second": float("nan")}, ValueError),
        ({"updates_per_second": True}, TypeError),
        ({"max_catch_up": 0}, ValueError),
        ({"max_catch_up": 1.5}, TypeError),
    ],
)
def test_invalid_layer_configuration_fails_before_start(kwargs, error):
    child = Probe()
    with pytest.raises(error):
        Layer(child, **kwargs)
    assert not child.events


def test_overlay_expiry_reveals_current_background_without_mutating_old_frame():
    background = {"text": "ABCDE"}
    overlay = TimedOverlay(ImageEffect("X", x=1, y=0), duration=0.5)
    scene = Scene(
        CallbackEffect(lambda buffer: buffer.put_at(0, 0, background["text"])), overlay
    )
    scene.start()
    try:
        first, second = Buffer(1, 5), Buffer(1, 5)
        scene.update(0.25)
        scene.draw(first)
        background["text"] = "12345"
        scene.update(0.25)
        scene.draw(second)
        assert first.buffer == [list("AXCDE")]
        assert second.buffer == [list("12345")]
        assert overlay.finished and scene.finished
    finally:
        scene.close()


def test_delayed_overlay_clamps_child_updates_and_closes_on_expiry():
    child = Probe()
    overlay = TimedOverlay(child, delay=1, duration=0.5)
    overlay.start()
    overlay.update(0.75)
    overlay.draw(Buffer(1, 1))
    assert not child.events and child.draws == 0
    overlay.update(0.5)
    assert child.events == ["start x"] and child.updates == [0.25]
    overlay.update(1)
    assert child.updates == [0.25, 0.25]
    assert child.events == ["start x", "close x"] and overlay.finished
    overlay.update(0)
    overlay.close()
    overlay.close()
    assert child.events.count("close x") == 1


@pytest.mark.parametrize("duration, delay, dt", [(0, 0, 1), (0.5, 1, 2)])
def test_invisible_window_never_acquires_child(duration, delay, dt):
    child = Probe()
    overlay = TimedOverlay(child, duration=duration, delay=delay)
    overlay.start()
    overlay.update(dt)
    overlay.close()
    assert overlay.finished and not child.events


def test_scene_completion_waits_for_delayed_overlay_and_finite_solver():
    playback = Playback([1], lambda state, buffer: None)
    overlay = TimedOverlay(ImageEffect("x"), delay=0.5, duration=0.5)
    scene = Scene(ImageEffect("endless"), playback, overlay)
    scene.start()
    try:
        scene.update(0)
        scene.update(0.1)
        assert playback.finished and not scene.finished
        scene.update(0.9)
        assert scene.finished
    finally:
        scene.close()


def test_pausing_solver_does_not_pause_background_or_overlay():
    child = Probe()
    playback = Playback([1, 2], lambda state, buffer: None, paused=True)
    overlay = TimedOverlay(ImageEffect("x"), duration=1)
    scene = Scene(Layer(child, updates_per_second=15), playback, overlay)
    scene.start()
    try:
        for _ in range(60):
            scene.update(1 / 60)
        assert len(child.updates) == 15
        assert playback.steps == 0 and overlay.finished
        playback.step()
        scene.update(0)
        assert playback.steps == 1
    finally:
        scene.close()


@pytest.mark.parametrize(
    "failure, delay", [("start", 0), ("start", 0.02), ("update", 0)]
)
def test_overlay_failures_close_child_once_and_scene_in_reverse(failure, delay):
    events = []
    first = Probe("first", events)
    child = Probe("child", events, failure=failure)
    last = Probe("last", events)
    scene = Scene(first, TimedOverlay(child, duration=1, delay=delay), last)
    clock = Clock()
    with pytest.raises(RuntimeError, match=failure):
        Player(RecordingScreen(), scene, frames=3, clock=clock, sleep=clock.sleep).run()
    assert events.count("close child") == 1
    assert events[-1] == "close first"
    if failure == "start" and delay == 0:
        assert "start last" not in events
    else:
        assert "close last" in events


@pytest.mark.parametrize("field", ["duration", "delay"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_overlay_validates_time_fields(field, value):
    with pytest.raises((TypeError, ValueError), match=field):
        TimedOverlay(Probe(), **{"duration": 1, field: value})


def test_overlay_close_before_start_is_safe_and_restart_is_explicitly_rejected():
    child = Probe()
    overlay = TimedOverlay(child, duration=1)
    overlay.close()
    overlay.close()
    assert child.events == []
    with pytest.raises(RuntimeError, match="single-use"):
        overlay.start()


def test_nested_regions_intersect_without_changing_child_coordinates():
    child = Scene(Layer(Probe(), region=(0, 0, 2, 2)))
    parent = Scene(Layer(child, region=(1, 1, 3, 2)))
    buffer = Buffer(3, 4).clear_buffer(val=".")
    parent.draw(buffer)
    assert ["".join(row) for row in buffer.buffer] == ["....", ".x..", "...."]


@pytest.mark.parametrize("dt", [-1, float("nan"), float("inf"), True, "1"])
def test_invalid_scene_dt_is_rejected_before_updating_any_child(dt):
    child = Probe()
    with pytest.raises((TypeError, ValueError), match="dt"):
        Scene(child).update(dt)
    assert child.updates == []


def test_delayed_overlay_activates_on_fractional_tick_boundary():
    child = Probe()
    overlay = TimedOverlay(child, delay=0.1, duration=1)
    overlay.start()
    for _ in range(6):
        overlay.update(1 / 60)
    overlay.draw(Buffer(1, 1))
    overlay.close()
    assert child.draws == 1
    assert child.events == ["start x", "close x"]
