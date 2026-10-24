"""An original public routing fixture with path, pulse and ripple overlays.

Run python -m bruhanimate.demos.routing_demo. Resize freely; q quits.
No puzzle input files or external resources are needed.
"""

from collections import deque
from collections.abc import Sequence

from bruhanimate import (
    AnimationSequence,
    Buffer,
    CallbackEffect,
    Layer,
    PathEffect,
    PulseEffect,
    ResizePolicy,
    RippleEffect,
    Scene,
    SequenceStep,
    SnowEffect,
    SnowSettings,
    TextStyle,
    draw_grid,
    play,
)

BOARD = (
    "#################",
    "#S....#.........#",
    "#.###.#.#####.#.#",
    "#...#...#.....#.#",
    "###.#####.#####.#",
    "#.............E.#",
    "#################",
)
SIZE = (len(BOARD[0]), len(BOARD))


def find_route(board: Sequence[str] = BOARD) -> tuple[tuple[int, int], ...]:
    """Breadth-first route on this demo's small public fixture; no library solver."""
    if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
        raise ValueError("board must be a non-empty rectangle")
    starts = [
        (x, y)
        for y, row in enumerate(board)
        for x, char in enumerate(row)
        if char == "S"
    ]
    ends = [
        (x, y)
        for y, row in enumerate(board)
        for x, char in enumerate(row)
        if char == "E"
    ]
    if (
        len(starts) != 1
        or len(ends) != 1
        or any(char not in "#.SE" for row in board for char in row)
    ):
        raise ValueError("board needs one S, one E, and only #/. corridor cells")
    start, end = starts[0], ends[0]
    queue = deque([start])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        point = queue.popleft()
        if point == end:
            route = []
            cursor: tuple[int, int] | None = point
            while cursor is not None:
                route.append(cursor)
                cursor = parent[cursor]
            return tuple(reversed(route))
        x, y = point
        for neighbor in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
            nx, ny = neighbor
            if (
                0 <= nx < len(board[0])
                and 0 <= ny < len(board)
                and board[ny][nx] != "#"
                and neighbor not in parent
            ):
                parent[neighbor] = point
                queue.append(neighbor)
    raise ValueError("destination is unreachable")


def build_scene(buffer: Buffer) -> Scene:
    """Keep the board/snow alive while a public sequence replaces the accents."""
    route = find_route()

    def trace() -> Scene:
        return Scene(
            Layer(
                PathEffect(
                    route,
                    size=SIZE,
                    spacing=(2, 1),
                    duration=3,
                    hold_duration=0.5,
                    mode="trace",
                    glyph="+",
                ),
                style=TextStyle(foreground=117, bold=True),
            )
        )

    def arrive() -> Scene:
        return Scene(
            Layer(
                RippleEffect(
                    route[-1], size=SIZE, spacing=(2, 1), radius=7, duration=2
                ),
                style=TextStyle(foreground=213),
            ),
            PulseEffect(
                route[-1],
                size=SIZE,
                spacing=(2, 1),
                duration=2,
                colors=(28, 34, 46, 231),
                glyph="E",
            ),
        )

    sequence = AnimationSequence(
        SequenceStep(
            lambda: PulseEffect(
                route[0], size=SIZE, spacing=(2, 1), duration=1.2, glyph="S"
            ),
            duration=1.2,
            gap=0.25,
            name="Source pulse",
        ),
        SequenceStep(trace, duration=3.5, gap=0.25, name="Trace route"),
        SequenceStep(
            lambda: PathEffect(route, size=SIZE, spacing=(2, 1), duration=2, trail=3),
            duration=2,
            name="Moving packet",
        ),
        SequenceStep(arrive, duration=2, gap=1, name="Arrival ripple"),
        repeat=True,
    )

    def board(target: Buffer) -> None:
        draw_grid(
            target,
            BOARD,
            spacing=(2, 1),
            glyph={
                "#": "\x1b[38;5;240m#\x1b[0m",
                ".": None,
                "S": "\x1b[92mS\x1b[0m",
                "E": "\x1b[92mE\x1b[0m",
            },
        )

    def captions(target: Buffer) -> None:
        target.put_at(0, 0, f"ROUTING | {sequence.phase_name}".ljust(target.width()))
        if target.height() > 1:
            target.put_at(
                0,
                target.height() - 1,
                "Grid coordinates | resize freely | q quit".ljust(target.width()),
            )

    return Scene(
        Layer(
            SnowEffect(buffer, " ", SnowSettings(seed=7, intensity=0.002)),
            updates_per_second=15,
        ),
        CallbackEffect(board),
        Layer(sequence, preserve_background=True),
        CallbackEffect(captions),
    )


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Play the repeating fixture with simulation timing independent of FPS."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_complete="hold",
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
