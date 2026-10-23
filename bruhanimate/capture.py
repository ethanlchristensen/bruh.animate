"""Streaming, terminal-free rendering and asciicast v2 recording."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal, TextIO

from .bruheffect.registry import effect_registry
from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen
from .grid import _glyph
from .player import Animation, EffectFactory, EffectSource, FramePresenter, Player

__all__ = ["Frame", "capture", "record"]


@dataclass(frozen=True)
class Frame:
    """An immutable snapshot delivered by capture, safe to retain across updates.

    index is zero-based; time is virtual seconds since playback began (first
    frame at zero). cells are rows of single-cell strings, including ANSI SGR
    styling. Unpainted transparent cells become spaces. No mutable Buffer escapes.
    """

    index: int
    time: float
    cells: tuple[tuple[str, ...], ...]

    @property
    def width(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    @property
    def height(self) -> int:
        return len(self.cells)

    def text(self) -> str:
        """Join rows with newlines, preserving ANSI SGR styling."""
        return "\n".join("".join(row) for row in self.cells)


class _HeadlessScreen(Screen):
    """Size/input boundary only: never initialize the platform Screen."""

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height

    def has_resized(self) -> bool:
        return False

    def get_event(self) -> None:
        return None


class _VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _CapturePresenter(FramePresenter):
    def __init__(self, clock: _VirtualClock, on_frame: Callable[[Frame], None]):
        self.clock = clock
        self.on_frame = on_frame
        self.index = 0

    def present(self, frame: Buffer) -> Buffer:
        snapshot = Frame(
            self.index,
            self.clock(),
            tuple(
                tuple(" " if cell is None else str(cell) for cell in row)
                for row in frame.buffer
            ),
        )
        self.on_frame(snapshot)
        self.index += 1
        # The snapshot has no references to mutable cells. Reuse this raster.
        return frame


def _player(
    effect: EffectSource | None,
    on_frame: Callable[[Frame], None],
    *,
    effect_factory: EffectFactory | None,
    width: int,
    height: int,
    fps: float,
    updates_per_second: float | None,
    frames: int | None,
    duration: float | None,
    on_complete: Literal["hold", "exit"],
    background: str,
    settings: object | None,
    preset: str | None,
    seed: int | None,
) -> Player:
    for name, value in (("width", width), ("height", height)):
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer")
        if value < 1:
            raise ValueError(f"{name} must be positive")
    if not callable(on_frame):
        raise TypeError("on_frame must be callable")
    if effect is not None and not isinstance(effect, (str, Animation)):
        raise TypeError("Expected a named effect or Animation")
    if effect_factory is not None and not callable(effect_factory):
        raise TypeError("effect_factory must be callable")
    if frames is None and duration is None:
        raise ValueError("Capture requires a finite frames or duration limit")
    if isinstance(fps, bool) or not isinstance(fps, (int, float)):
        raise TypeError("Capture fps must be a positive finite number")
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("Capture fps must be a positive finite number")
    _glyph(background)
    if isinstance(effect, str):
        settings = effect_registry.resolve_settings(
            effect, settings=settings, preset=preset, seed=seed
        )
    clock = _VirtualClock()
    player = Player(
        _HeadlessScreen(width, height),
        effect,
        effect_factory=effect_factory,
        fps=fps,
        updates_per_second=updates_per_second,
        frames=frames,
        duration=duration,
        on_complete=on_complete,
        background=background,
        settings=settings,
        preset=preset,
        seed=seed,
        presenter=_CapturePresenter(clock, on_frame),
        clock=clock,
        sleep=clock.sleep,
    )
    if updates_per_second is not None:
        # Player has validated both rates. Offline ticks never need to be dropped
        # to catch up with wall time; permit every tick between presentations.
        player.max_catch_up = max(5, math.ceil(updates_per_second / fps) + 1)
    if duration is not None:
        # The ideal presentation times are i / fps < duration. This also prevents
        # floating-point accumulation from admitting a frame at the deadline.
        limit = math.ceil(duration * fps)
        player.frames = limit if frames is None else min(frames, limit)
    return player


def capture(
    effect: EffectSource | None = None,
    *,
    on_frame: Callable[[Frame], None],
    effect_factory: EffectFactory | None = None,
    width: int = 80,
    height: int = 24,
    fps: float = 30,
    updates_per_second: float | None = None,
    frames: int | None = None,
    duration: float | None = None,
    on_complete: Literal["hold", "exit"] = "exit",
    background: str = " ",
    settings: object | None = None,
    preset: str | None = None,
    seed: int | None = None,
) -> int:
    """Render through Player into on_frame, without a terminal or real-time sleep.

    Supply a name, owned Animation, or effect_factory(buffer). A finite frames
    or duration limit is required; duration is virtual seconds, excluding startup
    and callback execution. fps must be positive. The first frame is at time zero
    after one update, matching Player. Fixed update rates never drop offline ticks.
    Completion exits by default. No input events or resizes are generated.

    Callbacks run synchronously; exceptions close owned content and propagate.
    Zero limits construct/start no content. Memory is bounded to the current
    raster/snapshot unless your callback retains frames. Animation resources
    still follow start/close: headless does not disable audio or custom devices.
    Repeatable output requires a seed, matching dimensions/settings/timing,
    dependency versions, and identical external inputs.

    Use effects.snow.capture(...) for effect-specific settings/preset completion.
    Returns the number of delivered frames.
    """
    return _player(
        effect,
        on_frame,
        effect_factory=effect_factory,
        width=width,
        height=height,
        fps=fps,
        updates_per_second=updates_per_second,
        frames=frames,
        duration=duration,
        on_complete=on_complete,
        background=background,
        settings=settings,
        preset=preset,
        seed=seed,
    ).run()


class _CastWriter:
    def __init__(self, stream: TextIO, width: int, height: int):
        self.stream = stream
        self.previous: Frame | None = None
        self._line({"version": 2, "width": width, "height": height})

    def _line(self, value: object) -> None:
        self.stream.write(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
        )

    def write(self, frame: Frame) -> None:
        changes = []
        if self.previous is None:
            changes.append("\x1b[0m\x1b[2J\x1b[H\x1b[?25l\x1b[?7l")
        for y, row in enumerate(frame.cells):
            for x, cell in enumerate(row):
                if self.previous is None or cell != self.previous.cells[y][x]:
                    _glyph(cell)
                    # Reset between cells so a colored cell cannot bleed into a plain one.
                    changes.append(f"\x1b[{y + 1};{x + 1}H\x1b[0m{cell}")
        if changes:
            self._line([frame.time, "o", "".join(changes)])
        self.previous = frame

    def finish(self) -> None:
        if self.previous is not None:
            # A final event preserves the timeline even after unchanged frames.
            self._line([self.previous.time, "o", "\x1b[0m\x1b[?7h\x1b[?25h"])


def record(
    effect: EffectSource | None,
    output: str | PathLike[str] | TextIO,
    *,
    effect_factory: EffectFactory | None = None,
    width: int = 80,
    height: int = 24,
    fps: float = 30,
    updates_per_second: float | None = None,
    frames: int | None = None,
    duration: float | None = None,
    on_complete: Literal["hold", "exit"] = "exit",
    background: str = " ",
    settings: object | None = None,
    preset: str | None = None,
    seed: int | None = None,
    overwrite: bool = False,
) -> int:
    """Stream headless capture to an asciicast v2 .cast path or borrowed text stream.

    Uses capture's virtual timing, bounds, seed and ownership contracts. Paths
    are UTF-8 and created exclusively unless overwrite=True; borrowed streams
    remain open and receive writes at their current position. Only output is
    recorded: no input, environment or host metadata. Changed cells use cursor
    addressing and ANSI SGR. Glyphs must occupy one cell; cursor/control escapes,
    wide and combining characters are rejected. Ambiguous-width glyphs assume
    one column. Failures close owned content/files and may leave a partial cast.

    Returns the number of captured frames. effects.snow.record(...) provides
    effect-specific preset and settings hints.
    """
    # Validate before opening/truncating an output file or starting content.
    player = _player(
        effect,
        lambda frame: None,
        effect_factory=effect_factory,
        width=width,
        height=height,
        fps=fps,
        updates_per_second=updates_per_second,
        frames=frames,
        duration=duration,
        on_complete=on_complete,
        background=background,
        settings=settings,
        preset=preset,
        seed=seed,
    )
    context = (
        Path(output).open("w" if overwrite else "x", encoding="utf-8", newline="\n")
        if isinstance(output, (str, PathLike))
        else nullcontext(output)
    )
    with context as stream:
        writer = _CastWriter(stream, width, height)
        presenter = player.presenter
        assert isinstance(presenter, _CapturePresenter)
        presenter.on_frame = writer.write
        try:
            return player.run()
        finally:
            writer.finish()
