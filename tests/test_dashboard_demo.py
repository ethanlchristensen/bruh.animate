import re

import pytest

from bruhanimate import Buffer, EventResult, FocusGroup, Playback, capture
from bruhanimate.demos.dashboard_demo import (
    DashboardControls,
    build_scene,
    draw_state,
    solve,
)


@pytest.mark.parametrize("size", [(80, 24), (40, 14), (5, 3), (1, 1)])
def test_dashboard_runs_to_frame_limit_with_valid_cells_at_all_sizes(size):
    playback = Playback(solve(), draw_state, steps_per_second=2)
    frames = []
    assert (
        capture(
            effect_factory=lambda buffer: build_scene(buffer, playback),
            on_frame=frames.append,
            width=size[0],
            height=size[1],
            frames=181,
            fps=30,
            updates_per_second=60,
            on_complete="hold",
        )
        == 181
    )
    for frame in (frames[0], frames[90], frames[-1]):
        assert len(frame.cells) == size[1] and all(
            len(row) == size[0] for row in frame.cells
        )
        for row in frame.cells:
            assert all(len(re.sub(r"\x1b\[[0-9;]*m", "", cell)) == 1 for cell in row)
    if size == (80, 24):
        text = re.sub(r"\x1b\[[0-9;]*m", "", frames[-1].text())
        assert "BEAM SOLVER" in text and "LIVE STATISTICS" in text
        assert "Complete" in text and "Splits  6" in text and "Exits   4" in text
        assert "q quit" in text and playback.finished


def test_pause_step_and_speed_update_labels_without_pausing_background():
    playback = Playback(solve(), draw_state, steps_per_second=2, paused=True)
    scene = build_scene(Buffer(24, 80), playback)
    scene.start()
    try:
        first, later = Buffer(24, 80), Buffer(24, 80)
        scene.draw(first)
        for _ in range(60):
            scene.update(1 / 60)
        scene.draw(later)
        assert playback.steps == 0 and first.buffer != later.buffer
        playback.handle_event(ord("n"))
        scene.update(1 / 60)
        assert playback.steps == 1 and playback.paused
        playback.handle_event(ord("+"))
        scene.update(1 / 60)
        scene.draw(later)
        text = re.sub(
            r"\x1b\[[0-9;]*m", "", "\n".join("".join(row) for row in later.buffer)
        )
        assert "Paused" in text and "Steps   1" in text
        assert f"Speed   {playback.steps_per_second:g}/s" in text
    finally:
        scene.close()


def test_focused_dashboard_controls_pause_independently_and_preserve_state_on_resize():
    playback = Playback(solve(), draw_state, steps_per_second=2)
    controls = DashboardControls(playback)
    scene = build_scene(Buffer(24, 80), playback, controls)
    scene.start()
    try:
        keys = controls.focus
        assert keys.focused is controls.solver_target
        assert not keys.handle_event(32)
        assert playback.paused and not controls.signal_paused
        keys.handle_event(9)
        assert keys.focused is controls.signal_target
        assert keys.help_text() == "space pause | r remix"
        assert not keys.handle_event(32)
        assert playback.paused and controls.signal_paused
        signal = controls.signal
        assert signal is not None
        phase = signal.t
        assert keys.dispatch(ord("n")) is EventResult.UNHANDLED
        first, later = Buffer(24, 80), Buffer(24, 80)
        scene.draw(first)
        for _ in range(60):
            scene.update(1 / 60)
        scene.draw(later)
        assert playback.steps == 0 and signal.t == phase
        assert first.buffer != later.buffer  # Snow keeps running.
        values = signal.vals[:]
        keys.handle_event(ord("r"))
        assert signal.vals != values and signal.t == phase
        keys.handle_event(-302)
        keys.handle_event(ord("n"))
        keys.handle_event(ord("+"))
        keys.handle_event(9)
        scene.update(1 / 60)
        assert playback.steps == 1 and playback.paused
        assert playback.steps_per_second == 4
        state = playback.state
        scene.resize((80, 12))  # Signal loses its layout allocation.
        assert not controls.signal_target.available
        assert keys.focused is controls.log_target
        scene.resize((80, 24))
        assert controls.signal_target.available
        assert keys.focused is controls.log_target
        assert playback.state is state and signal.t == phase
        scene.update(0)
        scene.draw(later)
        text = re.sub(
            r"\x1b\[[0-9;]*m", "", "\n".join("".join(row) for row in later.buffer)
        )
        assert "Focus   log" in text and "Signal  Paused" in text
        scene.resize((1, 1))
        assert keys.focused is None and keys.handle_event(ord("q"))
    finally:
        scene.close()
    assert controls.focus.focused is None


def test_dashboard_run_uses_focus_handler(monkeypatch):
    from bruhanimate.demos import dashboard_demo

    def play(**options):
        scene = options["effect_factory"](Buffer(24, 80))
        scene.start()
        try:
            assert options["on_resize"] == "resize"
            handler = options["event_handler"]
            assert isinstance(handler.__self__, FocusGroup)
            assert not handler(9) and handler.__self__.focused.name == "signal"
            assert handler(ord("q"))
        finally:
            scene.close()
        return 7

    monkeypatch.setattr(dashboard_demo, "play", play)
    assert dashboard_demo.run(frames=7) == 7


def test_activity_log_records_actions_and_progress_once_outside_draw():
    playback = Playback(solve(), draw_state, steps_per_second=2, paused=True)
    controls = DashboardControls(playback)
    scene = build_scene(Buffer(24, 80), playback, controls)
    scene.start()
    try:
        keys = controls.focus
        keys.handle_event(ord("n"))
        assert playback.steps == 0
        scene.update(0)
        assert playback.steps == 1
        assert "Solver step requested" in controls.log.lines
        assert "Step 1: 0 splits, 0 exits" in controls.log.lines
        before = controls.log.lines
        scene.draw(Buffer(24, 80))
        scene.draw(Buffer(24, 80))
        scene.update(0)
        assert controls.log.lines == before
        keys.handle_event(ord("+"))
        keys.handle_event(32)
        keys.handle_event(9)
        keys.handle_event(32)
        keys.handle_event(ord("r"))
        keys.handle_event(9)
        assert keys.focused is controls.log_target
        assert controls.status() == "log LIVE"
        keys.handle_event(-200)
        assert not controls.log.follow_tail and controls.status() == "log HISTORY"
        offset = controls.log.offset
        for _ in range(80):
            scene.update(0.1)
        assert playback.finished and controls.log.lines.count("Solver complete") == 1
        assert controls.log.offset == offset
        assert "Solver speed: 4 steps/sec" in controls.log.lines
        assert "Solver resumed" in controls.log.lines
        assert "Signal paused" in controls.log.lines
        assert "Signal pattern remixed" in controls.log.lines
        state = playback.state
        steps = playback.steps
        keys.handle_event(-208)  # Page Down only scrolls the focused log.
        assert playback.state is state and playback.steps == steps
        lines = controls.log.lines
        scene.resize((40, 14))
        scene.resize((80, 24))
        assert controls.log.lines == lines and not controls.log.follow_tail
        keys.handle_event(-201)
        assert controls.log.follow_tail and controls.log.at_bottom
        for i in range(300):
            controls.log.append(f"message {i}")
        assert controls.log.line_count == 200
    finally:
        scene.close()


def test_solver_canvas_scrolls_without_consuming_snapshots_and_resets_neither_on_resize():
    playback = Playback(solve(), draw_state, paused=True)
    controls = DashboardControls(playback)
    scene = build_scene(Buffer(14, 40), playback, controls)
    scene.start()
    try:
        controls.focus.focus("solver")
        controls.focus.handle_event(-205)  # Right pans, n steps in this demo.
        controls.focus.handle_event(-206)
        assert controls.solver_view.offset == (1, 1)
        assert playback.steps == 0
        controls.focus.handle_event(ord("n"))
        scene.update(0)
        state = playback.state
        scene.resize((50, 16))
        assert controls.solver_view.offset == (1, 1)
        assert playback.steps == 1 and playback.state is state
    finally:
        scene.close()
