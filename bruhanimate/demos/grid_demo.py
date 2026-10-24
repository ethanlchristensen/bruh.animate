"""A public maze fixture: pure BFS snapshots plus a small playback composition.

Run python -m bruhanimate.demos.grid_demo. Space pauses, n/right steps,
+/- changes speed, and q quits. The final path remains visible until quit.
"""

from collections import deque
from dataclasses import dataclass

from bruhcolor import bruhcolored

from bruhanimate import (
    CallbackEffect,
    Playback,
    ResizePolicy,
    Scene,
    draw_grid,
    effect_registry,
    play,
)

MAZE = (
    "#############",
    "#S..#.......#",
    "#.#.#.#####.#",
    "#.#...#...#.#",
    "#.#####.#.#.#",
    "#.......#..E#",
    "#############",
)

Point = tuple[int, int]


@dataclass(frozen=True)
class SearchState:
    current: Point
    visited: frozenset[Point]
    frontier: frozenset[Point]
    path: tuple[Point, ...] = ()
    complete: bool = False


def solve(board=MAZE):
    """Yield immutable BFS snapshots without terminal access or retained history.

    This small example copies sets into snapshots; large searches should sample
    or aggregate progress rather than produce a snapshot of every branch.
    """
    if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
        raise ValueError("Maze must be a non-empty rectangle")
    starts = [
        (x, y)
        for y, row in enumerate(board)
        for x, cell in enumerate(row)
        if cell == "S"
    ]
    ends = [
        (x, y)
        for y, row in enumerate(board)
        for x, cell in enumerate(row)
        if cell == "E"
    ]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("Maze needs exactly one S and one E")
    queue = deque(starts)
    parents = {starts[0]: None}
    visited = set()
    while queue:
        current = queue.popleft()
        visited.add(current)
        if current == ends[0]:
            path = []
            point = current
            while point is not None:
                path.append(point)
                point = parents[point]
            yield SearchState(
                current,
                frozenset(visited),
                frozenset(queue),
                tuple(reversed(path)),
                True,
            )
            return
        x, y = current
        for nx, ny in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
            if (
                0 <= ny < len(board)
                and 0 <= nx < len(board[0])
                and board[ny][nx] != "#"
                and (nx, ny) not in parents
            ):
                parents[nx, ny] = current
                queue.append((nx, ny))
        yield SearchState(current, frozenset(visited), frozenset(queue))


WALL = bruhcolored("#", color=240).colored
VISITED = bruhcolored(".", color=39).colored
FRONTIER = bruhcolored("o", color=220).colored
PATH = bruhcolored("*", color=46).colored
CURSOR = bruhcolored("@", color=231).colored


def draw_state(state, buffer):
    def glyph(cell, column, row):
        if cell == "#":
            return WALL
        if (column, row) in state.frontier:
            return FRONTIER
        if (column, row) in state.visited:
            return VISITED
        return cell if cell in "SE" else None

    grid = draw_grid(
        buffer,
        MAZE,
        glyph=glyph,
        spacing=(2, 1),
        region=(0, 1, buffer.width(), max(0, buffer.height() - 2)),
    )
    grid.path(state.path, PATH)
    grid.put(*state.current, CURSOR)


def run(*, frames=None, fps=60, on_resize: ResizePolicy = "resize"):
    playback = Playback(solve(), draw_state, steps_per_second=10)

    def status(buffer):
        state = playback.state
        mode = (
            "Solved"
            if state and state.complete
            else "Paused"
            if playback.paused
            else "Searching"
        )
        buffer.put_at(
            0, 0, f"{mode} | {playback.steps} states | {playback.steps_per_second:g}/s"
        )
        buffer.put_at(
            0, buffer.height() - 1, "Space pause | n/right step | +/- speed | q quit"
        )

    def build(buffer):
        return Scene(
            effect_registry.create("stars", buffer, " ", preset="color"),
            playback,
            CallbackEffect(status),
        )

    return play(
        effect_factory=build,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        event_handler=playback.handle_event,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
