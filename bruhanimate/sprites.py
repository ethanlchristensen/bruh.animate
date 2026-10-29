"""Immutable cell art and clips, with independently owned sprite instances."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import floor

from ._clock import _CycleClock
from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .geometry import Point, Rect, _clip, _integers, _rect
from .grid import _glyph
from .panel import _pair
from .resize import _size


@dataclass(frozen=True, slots=True, init=False)
class SpriteAsset:
    """An immutable rectangular frame of single-cell strings or transparent None.

    Input rows are copied and validated. Spaces paint. ANSI SGR styling belongs
    inside each cell string; wide/combining glyphs and cursor escapes are rejected.
    Assets have no lifecycle and may be shared between any number of sprites.
    """

    cells: tuple[tuple[str | None, ...], ...]

    def __init__(self, rows: Sequence[Sequence[str | None]]) -> None:
        cells = tuple(
            tuple(None if cell is None else _glyph(cell) for cell in row)
            for row in rows
        )
        if not cells or not cells[0] or any(len(row) != len(cells[0]) for row in cells):
            raise ValueError("sprite rows must form a non-empty rectangle")
        object.__setattr__(self, "cells", cells)

    @classmethod
    def from_text(cls, text: str, *, transparent: str | None = None) -> SpriteAsset:
        """Copy plain multiline art; pad short rows with transparent cells.

        ``transparent`` optionally replaces one plain character with None.
        Use the cell-based constructor for styled glyphs.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if transparent is not None:
            _glyph(transparent)
            if len(transparent) != 1:
                raise ValueError("transparent must be one plain character")
        rows = text.splitlines()
        width = max(map(len, rows), default=0)
        return cls(
            [
                [None if cell == transparent else cell for cell in row]
                + [None] * (width - len(row))
                for row in rows
            ]
        )

    @property
    def width(self) -> int:
        return len(self.cells[0])

    @property
    def height(self) -> int:
        return len(self.cells)


@dataclass(frozen=True, slots=True, init=False)
class SpriteClip:
    """Immutable equally sized frames, each held for frame_duration seconds.

    Repeat loops indefinitely; a finite clip holds its last frame on completion.
    Clips contain no playback state and can be shared safely.
    """

    frames: tuple[SpriteAsset, ...]
    frame_duration: float
    repeat: bool

    def __init__(
        self,
        frames: Sequence[SpriteAsset],
        *,
        frame_duration: float = 0.1,
        repeat: bool = True,
    ) -> None:
        copied = tuple(frames)
        if not copied:
            raise ValueError("a clip needs at least one frame")
        if any(not isinstance(frame, SpriteAsset) for frame in copied):
            raise TypeError("clip frames must be SpriteAsset instances")
        if any(
            (frame.width, frame.height) != (copied[0].width, copied[0].height)
            for frame in copied
        ):
            raise ValueError("clip frames must have equal dimensions")
        _seconds(frame_duration, "frame_duration")
        # The shared clock also validates positive durations, repeat and overflow.
        _CycleClock(frame_duration * len(copied), repeat, 0, 0)
        object.__setattr__(self, "frames", copied)
        object.__setattr__(self, "frame_duration", float(frame_duration))
        object.__setattr__(self, "repeat", repeat)


class Sprite:
    """A single-use, independently timed instance of a shared asset or clip.

    Position and velocity are (columns, rows) and (columns/sec, rows/sec).
    Position is floored at draw time; origin is an integer anchor subtracted
    from it. Flips affect frame cells around that fixed anchor. Optional clip
    is a destination (x, y, width, height) rectangle. Resize retains all state.

    Start before update. Draw is pure, clipped, and allowed before start. Hidden
    sprites still advance; visibility only suppresses drawing. Finite clips
    report finished after every frame's duration has elapsed, hold the final
    frame, and keep moving. Static assets and repeating clips report None.
    Input is routed explicitly through Player; sprites do not poll or forward it.
    """

    def __init__(
        self,
        source: SpriteAsset | SpriteClip,
        *,
        position: tuple[float, float] = (0, 0),
        velocity: tuple[float, float] = (0, 0),
        origin: Point = (0, 0),
        flip_x: bool = False,
        flip_y: bool = False,
        clip: Rect | None = None,
    ) -> None:
        if not isinstance(source, (SpriteAsset, SpriteClip)):
            raise TypeError("source must be a SpriteAsset or SpriteClip")
        _integers(origin, 2, "origin")
        if type(flip_x) is not bool or type(flip_y) is not bool:
            raise TypeError("flips must be bools")
        if clip is not None:
            _rect(clip, "clip")
        self._source = source
        self._position = _pair(position, "position")
        self._velocity = _pair(velocity, "velocity")
        self._origin, self._flip_x, self._flip_y, self._clip = (
            origin,
            flip_x,
            flip_y,
            clip,
        )
        self._clock = (
            _CycleClock(len(source.frames) * source.frame_duration, source.repeat, 0, 0)
            if isinstance(source, SpriteClip)
            else None
        )
        self._visible = True
        self._started = self._closed = False

    @property
    def source(self) -> SpriteAsset | SpriteClip:
        return self._source

    @property
    def position(self) -> tuple[float, float]:
        return self._position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self._position = _pair(value, "position")

    @property
    def velocity(self) -> tuple[float, float]:
        return self._velocity

    @velocity.setter
    def velocity(self, value: tuple[float, float]) -> None:
        self._velocity = _pair(value, "velocity")

    @property
    def frame_index(self) -> int:
        if isinstance(self.source, SpriteAsset) or self._clock is None:
            return 0
        fraction = self._clock.time / self.source.frame_duration
        return min(len(self.source.frames) - 1, floor(fraction + 1e-9))

    @property
    def finished(self) -> bool | None:
        if self._clock is None or self._clock.repeat:
            return None
        return self._clock.time >= self._clock.duration

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("Sprite is single-use; construct a new instance")
        self._started = True

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Sprite must be started and not closed before update")
        _seconds(dt, "dt")
        # Validate motion before committing either position or the clip clock.
        position = _pair(
            (
                self.position[0] + self.velocity[0] * dt,
                self.position[1] + self.velocity[1] * dt,
            ),
            "updated position",
        )
        if self._clock is not None:
            self._clock.update(dt)
        self._position = position

    def set_visible(self, visible: bool) -> None:
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        self._visible = visible

    def resize(self, size: tuple[int, int]) -> None:
        """Validate the viewport notification without resetting position or time."""
        _size(size)

    def draw(self, buffer: Buffer) -> None:
        if not self._visible or self._closed:
            return
        frame = (
            self.source
            if isinstance(self.source, SpriteAsset)
            else self.source.frames[self.frame_index]
        )
        x, y = (
            floor(self.position[0]) - self._origin[0],
            floor(self.position[1]) - self._origin[1],
        )
        left, top, right, bottom = _clip(buffer, self._clip)
        for row in range(max(top, y), min(bottom, y + frame.height)):
            sy = frame.height - 1 - (row - y) if self._flip_y else row - y
            for column in range(max(left, x), min(right, x + frame.width)):
                sx = frame.width - 1 - (column - x) if self._flip_x else column - x
                cell = frame.cells[sy][sx]
                if cell is not None:
                    buffer.put_char(column, row, cell)

    def close(self) -> None:
        self._closed = True
