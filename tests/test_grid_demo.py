import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import Buffer, Playback, Player
from bruhanimate.demos.grid_demo import MAZE, draw_state, solve


def test_pure_solver_finds_a_valid_shortest_path_on_a_public_fixture():
    final = None
    for state in solve():
        final = state
    assert final.complete
    assert final.path[0] == (1, 1)
    assert final.path[-1] == (11, 5)
    # The route via the upper corridor takes 18 orthogonal moves.
    assert len(final.path) == 19
    assert all(MAZE[y][x] != "#" for x, y in final.path)
    assert all(
        abs(x1 - x2) + abs(y1 - y2) == 1
        for (x1, y1), (x2, y2) in zip(final.path, final.path[1:])
    )


def test_solver_snapshots_are_independent_and_draw_twice_without_advancing():
    source = solve()
    first = next(source)
    visited = first.visited
    second = next(source)
    assert first.visited == visited and first.visited != second.visited
    one, two = Buffer(12, 40), Buffer(12, 40)
    draw_state(second, one)
    draw_state(second, two)
    assert one.buffer == two.buffer
    source.close()


def test_same_solver_runs_to_completion_through_player():
    playback = Playback(solve(), draw_state, steps_per_second=30)
    clock = Clock()
    screen = RecordingScreen()
    screen.height, screen.width = 12, 40
    result = Player(
        screen, playback, on_complete="exit", fps=30, clock=clock, sleep=clock.sleep
    ).run()
    assert playback.finished and playback.state.complete
    assert result == playback.steps + 1


@pytest.mark.parametrize("board", [[], [""], ["S#", "E"], ["..."], ["SSE"]])
def test_solver_reports_invalid_input(board):
    with pytest.raises(ValueError, match="Maze"):
        next(solve(board))
