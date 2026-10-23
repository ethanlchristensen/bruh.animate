import pytest

from bruhanimate import Buffer, Playback, capture
from bruhanimate.demos.beam_demo import BOARD, build_scene, draw_state, solve


def test_public_fixture_splits_and_merges_without_enumerating_histories():
    states = list(solve())
    assert len(states) == len(BOARD) + 1
    assert states[0].active == frozenset({(7, 0)})
    assert states[3].active == frozenset({(6, 3), (8, 3)})
    assert states[5].active == frozenset({(5, 5), (7, 5), (9, 5)})
    assert states[-1].complete and not states[-1].active
    assert states[-1].splits == 6 and states[-1].exits == 4
    assert all(len(state.active) <= len(BOARD[0]) for state in states)
    assert states[0].visited == frozenset({(7, 0)})


def test_side_exits_are_counted_and_plain_beams_fall_straight():
    assert list(solve(("S", "^")))[-1].exits == 2
    assert list(solve(("S", ".")))[-1].exits == 1


@pytest.mark.parametrize(
    "board", [(), ("",), ("S.", "."), ("...",), ("SS",), ("..", ".S"), ("S?",)]
)
def test_invalid_boards_fail_without_terminal_access(board):
    with pytest.raises(ValueError, match="Beam board"):
        next(solve(board))


def test_drawing_is_readonly_and_clipped_to_panel():
    state = list(solve())[5]
    first, second = Buffer(16, 50), Buffer(16, 50)
    draw_state(state, first)
    draw_state(state, second)
    assert first.buffer == second.buffer
    assert all(
        cell == " " for row in (first.buffer[0], first.buffer[-1]) for cell in row
    )


@pytest.mark.parametrize("fps", [30, 60])
@pytest.mark.parametrize("size", [(50, 16), (5, 3), (1, 1)])
def test_complete_scene_runs_headlessly_at_small_and_normal_sizes(fps, size):
    playback = Playback(solve(), draw_state, steps_per_second=5)
    snapshots = []
    assert (
        capture(
            effect_factory=lambda buffer: build_scene(buffer, playback),
            on_frame=snapshots.append,
            width=size[0],
            height=size[1],
            fps=fps,
            updates_per_second=60,
            duration=5,
        )
        > 0
    )
    assert playback.finished and playback.state.complete
    assert playback.state.splits == 6 and playback.state.exits == 4
    assert all(
        frame.width == size[0] and frame.height == size[1] for frame in snapshots
    )
    if size[0] == 50:
        assert "Complete" in snapshots[-1].text()
        assert any("Watch ^ split" in frame.text() for frame in snapshots)
        assert "Watch ^ split" not in snapshots[-1].text()


def test_pause_and_step_keep_overlay_and_snow_independent():
    playback = Playback(solve(), draw_state, steps_per_second=5, paused=True)
    scene = build_scene(Buffer(16, 50), playback)
    scene.start()
    try:
        snow, _, intro, _ = [layer.animation for layer in scene.layers]
        before = snow.rng.getstate()
        for _ in range(120):
            scene.update(1 / 60)
        assert playback.steps == 0 and intro.finished
        assert snow.rng.getstate() != before
        playback.handle_event(ord("n"))
        scene.update(1 / 60)
        assert playback.steps == 1 and playback.paused
        playback.handle_event(ord(" "))
        playback.handle_event(ord("+"))
        for _ in range(60):
            scene.update(1 / 60)
        assert playback.state.complete
    finally:
        scene.close()
