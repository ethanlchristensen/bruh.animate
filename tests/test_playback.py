from copy import deepcopy
from itertools import count
from unittest.mock import Mock

import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import (
    Buffer,
    CallbackEffect,
    ImageEffect,
    Playback,
    Player,
    Scene,
    Screen,
    play,
)


def test_source_is_lazy_and_drawing_does_not_consume_it():
    events = []

    def states():
        try:
            for value in count():
                events.append(value)
                yield value
        finally:
            events.append("closed")

    playback = Playback(
        states(), lambda state, buffer: buffer.put_char(0, 0, str(state))
    )
    assert events == []
    playback.start()
    playback.start()
    assert events == []
    playback.update(0)
    first, second = Buffer(1, 1), Buffer(1, 1)
    playback.draw(first)
    playback.draw(second)
    assert first.buffer == second.buffer == [["0"]]
    assert events == [0]
    playback.close()
    playback.close()
    assert events == [0, "closed"]


@pytest.mark.parametrize("fps", [30, 60])
def test_solver_progress_is_independent_of_display_fps(fps):
    playback = Playback(count(), lambda state, buffer: None, steps_per_second=10)
    clock = Clock()
    Player(
        RecordingScreen(), playback, fps=fps, frames=fps, clock=clock, sleep=clock.sleep
    ).run()
    assert playback.steps == 10
    assert playback.state == 9
    assert not playback.finished


def test_pause_step_and_resume_discard_paused_wall_time():
    playback = Playback(count(), lambda state, buffer: None, steps_per_second=10)
    playback.start()
    try:
        playback.update(0)
        playback.pause()
        playback.update(100)
        assert playback.steps == 1
        playback.step()
        assert playback.steps == 1  # input queues a logical step, never calls next()
        playback.update(100)
        assert playback.steps == 2
        assert playback.paused
        playback.resume()
        playback.update(100)
        assert playback.steps == 2
        playback.update(0.1)
        assert playback.steps == 3
    finally:
        playback.close()


def test_initially_paused_source_waits_for_a_step():
    playback = Playback([None, 42], lambda state, buffer: None, paused=True)
    playback.start()
    try:
        playback.update(10)
        assert not playback.has_state
        playback.step()
        playback.update(10)
        assert playback.has_state and playback.state is None
        playback.update(10)
        assert playback.steps == 1
    finally:
        playback.close()


def test_stalls_and_queued_steps_have_bounded_work():
    playback = Playback(count(), lambda state, buffer: None, max_catch_up=2)
    playback.start()
    try:
        playback.update(0)
        playback.update(100)
        assert playback.steps == 3
        playback.update(0)
        assert playback.steps == 3
        for _ in range(5):
            playback.step()
        playback.update(100)
        assert playback.steps == 5
        playback.update(0)
        assert playback.steps == 7
        playback.update(0)
        assert playback.steps == 8
    finally:
        playback.close()


def test_optional_copy_isolates_a_producer_that_reuses_mutable_state():
    shared = {"value": 1}

    def source():
        yield shared
        shared["value"] = 2
        yield shared

    playback = Playback(source(), lambda state, buffer: None, copy_state=deepcopy)
    playback.start()
    try:
        playback.update(0)
        first = playback.state
        playback.update(0.1)
        assert first == {"value": 1}
        assert playback.state == {"value": 2}
        assert playback.state is not shared
    finally:
        playback.close()


def test_exhaustion_closes_source_once_and_keeps_final_snapshot():
    class Source:
        def __init__(self):
            self.values = iter(["X"])
            self.close = Mock()

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.values)

    source = Source()
    playback = Playback(source, lambda state, buffer: buffer.put_char(0, 0, state))
    playback.start()
    playback.update(0)
    assert not playback.finished
    playback.update(0.1)
    playback.update(10)
    buffer = Buffer(1, 1)
    playback.draw(buffer)
    assert playback.finished and playback.steps == 1
    assert buffer.buffer == [["X"]]
    playback.close()
    source.close.assert_called_once()


@pytest.mark.parametrize("on_complete, frames", [("hold", 8), ("exit", 3)])
def test_player_completion_holds_or_exits_after_presenting_final_state(
    on_complete, frames
):
    clock, screen = Clock(), RecordingScreen()
    playback = Playback(
        ["A", "B"],
        lambda state, buffer: buffer.put_char(0, 0, state),
        steps_per_second=10,
    )
    scene = Scene(Scene(ImageEffect("background")), Scene(playback))
    player = Player(
        screen,
        scene,
        frames=8,
        fps=10,
        on_complete=on_complete,
        clock=clock,
        sleep=clock.sleep,
    )
    assert player.run() == frames
    assert player.presenter.last_displayed.get_char(0, 0) == "B"
    assert scene.finished and playback.finished


def test_empty_source_exits_with_one_background_frame():
    draw = Mock()
    playback = Playback([], draw)
    assert Player(RecordingScreen(), playback, on_complete="exit", fps=None).run() == 1
    assert playback.finished and not playback.has_state
    draw.assert_not_called()


def test_scene_waits_for_all_finite_children_and_ignores_endless_content():
    first, second = Playback([], Mock()), Playback([1], Mock())
    scene = Scene(first, second, Scene(ImageEffect("endless")))
    assert Scene(ImageEffect("endless")).finished is None
    scene.start()
    try:
        scene.update(0)
        assert first.finished and not scene.finished
        scene.update(0.1)
        assert scene.finished
    finally:
        scene.close()


def test_play_forwards_input_and_completion_options(monkeypatch):
    screen = RecordingScreen(events=[ord("n"), None, ord("q")])
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    playback = Playback(count(), Mock(), paused=True)
    assert (
        play(
            playback, event_handler=playback.handle_event, on_complete="exit", fps=None
        )
        == 1
    )
    assert playback.steps == 1 and screen.closed


def test_keyboard_controls_route_normalized_events():
    playback = Playback(count(), Mock())
    assert not playback.handle_event(ord(" ")) and playback.paused
    assert not playback.handle_event(Screen.KEY_RIGHT)
    assert not playback.handle_event(ord("p")) and not playback.paused
    playback.handle_event(ord("+"))
    assert playback.steps_per_second == 20
    playback.handle_event(ord("-"))
    assert playback.steps_per_second == 10
    assert playback.handle_event(ord("q"))
    assert playback.handle_event(27)


def test_player_keeps_presenting_while_only_the_solver_is_paused():
    playback = Playback(count(), Mock(), paused=True)
    clock = Clock()
    screen = RecordingScreen(events=[None, ord("n"), None, None, ord("q")])
    background_updates = []
    scene = Scene(CallbackEffect(Mock(), update=background_updates.append), playback)
    player = Player(
        screen,
        scene,
        event_handler=playback.handle_event,
        fps=30,
        clock=clock,
        sleep=clock.sleep,
    )
    assert player.run() == 3
    assert screen.batches == 3 and playback.steps == 1
    assert len(background_updates) == 3


def test_zero_frames_never_iterates_or_starts_the_source():
    source = Mock()
    source.__iter__ = Mock(side_effect=AssertionError("iterated"))
    playback = Playback(source, Mock())
    assert Player(RecordingScreen(), playback, frames=0).run() == 0
    source.__iter__.assert_not_called()
    assert not playback.has_state


def test_speed_change_discards_accumulated_time():
    playback = Playback(count(), Mock(), steps_per_second=10)
    playback.start()
    try:
        playback.update(0)
        playback.update(0.09)
        playback.steps_per_second = 20
        playback.update(100)
        assert playback.steps == 1
        playback.update(0.05)
        assert playback.steps == 2
    finally:
        playback.close()


@pytest.mark.parametrize("failure", ["source", "draw", "copy"])
def test_playback_errors_close_generator_and_restore_owned_screen(failure, monkeypatch):
    screen = RecordingScreen()
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    closed = []

    def source():
        try:
            if failure == "source":
                raise ValueError("source failed")
            yield 1
        finally:
            closed.append(True)

    fail = Mock(side_effect=ValueError(f"{failure} failed"))
    playback = Playback(
        source(),
        fail if failure == "draw" else Mock(),
        copy_state=fail if failure == "copy" else None,
    )
    with pytest.raises(ValueError, match=failure):
        play(playback, frames=1, fps=None)
    assert closed == [True] and screen.closed


def test_playback_is_single_use_and_update_requires_start():
    playback = Playback([], Mock())
    with pytest.raises(RuntimeError, match="started"):
        playback.update(0)
    playback.close()
    with pytest.raises(RuntimeError, match="single-use"):
        playback.start()


@pytest.mark.parametrize("rate", [0, -1, float("inf"), float("nan")])
def test_invalid_source_rates_are_rejected(rate):
    with pytest.raises(ValueError, match="steps_per_second"):
        Playback([], Mock(), steps_per_second=rate)


@pytest.mark.parametrize("dt", [-1, float("inf"), float("nan")])
def test_invalid_deltas_are_rejected_without_advancing(dt):
    playback = Playback([1], Mock())
    playback.start()
    try:
        with pytest.raises(ValueError, match="dt"):
            playback.update(dt)
        assert playback.steps == 0
    finally:
        playback.close()
