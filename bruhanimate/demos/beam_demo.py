"""Falling beams on an original public fixture, with independently paced layers.

Run python -m bruhanimate.demos.beam_demo. Space pauses the solver, n/right
steps, +/- changes solver speed, and q quits. Snow and the introductory overlay
keep advancing while the solver is paused. No files or puzzle inputs are needed.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from bruhanimate import (
    Buffer,
    CallbackEffect,
    ImageEffect,
    Layer,
    Playback,
    Scene,
    TimedOverlay,
    draw_grid,
    effect_registry,
    play,
)

# Original fixture: ^ sends a downward beam diagonally left/right to the next
# row. Beams meeting in a cell merge; we never enumerate exponential histories.
BOARD = (
    ".......S.......",
    "...............",
    ".......^.......",
    "...............",
    "......^.^......",
    "...............",
    ".....^.^.^.....",
    "...............",
    "...............",
)
Point = tuple[int, int]


@dataclass(frozen=True)
class BeamState:
    active: frozenset[Point]
    visited: frozenset[Point]
    splits: int = 0
    exits: int = 0
    complete: bool = False


def solve(board: Sequence[str] = BOARD) -> Iterator[BeamState]:
    """Yield one immutable snapshot per row, retaining only current board state.

    Cells are '.', '^', or a single top-row 'S'. Splits take effect on the next
    row; out-of-bounds branches exit and coincident branches merge. This is a
    small visualization example, not an Advent of Code solution or input.
    """
    if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
        raise ValueError("Beam board must be a non-empty rectangle")
    if any(cell not in ".^S" for row in board for cell in row):
        raise ValueError("Beam board supports only '.', '^', and 'S'")
    starts = {
        (x, y)
        for y, row in enumerate(board)
        for x, cell in enumerate(row)
        if cell == "S"
    }
    if len(starts) != 1 or next(iter(starts))[1] != 0:
        raise ValueError("Beam board needs exactly one S in the top row")
    active, visited = starts, set(starts)
    splits = exits = 0
    yield BeamState(frozenset(active), frozenset(visited))
    while active:
        following = set()
        for x, y in sorted(active):
            split = board[y][x] == "^"
            splits += int(split)
            for nx in (x - 1, x + 1) if split else (x,):
                if 0 <= nx < len(board[0]) and y + 1 < len(board):
                    following.add((nx, y + 1))
                else:
                    exits += 1
        active = following
        visited.update(active)
        yield BeamState(
            frozenset(active), frozenset(visited), splits, exits, not active
        )


def draw_state(state: BeamState, buffer: Buffer) -> None:
    """Draw only current state; puzzle-specific glyphs stay in the demo."""

    def glyph(cell: str, column: int, row: int) -> str | None:
        if (column, row) in state.active:
            return "\x1b[93m*\x1b[0m"
        if cell == "^":
            return "\x1b[96m^\x1b[0m"
        if (column, row) in state.visited:
            return "\x1b[92m|\x1b[0m"
        return "S" if cell == "S" else None

    draw_grid(
        buffer,
        BOARD,
        glyph=glyph,
        spacing=(2, 1),
        region=(1, 2, max(0, buffer.width() - 2), max(0, buffer.height() - 4)),
    )


def build_scene(buffer: Buffer, playback: Playback[BeamState]) -> Scene:
    """Compose a clipped snow panel, solver, timed message, and status display."""
    width, height = buffer.width(), buffer.height()
    panel = (1, 2, max(0, width - 2), max(0, height - 4))

    def status(target: Buffer) -> None:
        state = playback.state
        mode = (
            "Complete"
            if state and state.complete
            else "Paused"
            if playback.paused
            else "Running"
        )
        target.put_at(0, 0, f"Beams | {mode} | {playback.steps_per_second:g} steps/s")
        if height > 3:
            target.put_at(0, 1, "-" * width)
            summary = f" splits {state.splits if state else 0} | exits {state.exits if state else 0} "
            target.put_at(0, height - 2, summary.ljust(width, "-"))
        if height > 1:
            target.put_at(0, height - 1, "Space pause | n step | +/- speed | q quit")

    snow = effect_registry.create("snow", buffer, " ", preset="moderate", seed=42)
    return Scene(
        Layer(snow, region=panel, updates_per_second=15),
        Layer(playback, region=panel),  # Playback's own solver clock runs at 5/s.
        Layer(
            TimedOverlay(ImageEffect("  Watch ^ split the beams  "), duration=1),
            region=panel,
        ),
        CallbackEffect(status),
    )


def run(*, frames: int | None = None, fps: float = 60) -> int:
    """Play the demo natively; hold the completed board until quit/frame limit."""
    playback = Playback(solve(), draw_state, steps_per_second=5)
    return play(
        effect_factory=lambda buffer: build_scene(buffer, playback),
        frames=frames,
        fps=fps,
        updates_per_second=60,
        event_handler=playback.handle_event,
    )


if __name__ == "__main__":
    run()
