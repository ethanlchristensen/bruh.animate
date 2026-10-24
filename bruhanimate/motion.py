"""Transparent, simulation-timed accents in board coordinates."""

from collections.abc import Sequence
from math import floor, hypot
from typing import Literal

from .bruhutil import Buffer
from .grid import GridViewport, _glyph
from .image import _CycleClock
from .resize import _size
from .scene import _seconds
from .styling import TextStyle

Cell = tuple[int, int]
PathMode = Literal["pulse", "trace"]
RippleMetric = Literal["euclidean", "manhattan", "chebyshev"]


def _point(point: Cell, size: tuple[int, int]) -> Cell:
    if (
        not isinstance(point, tuple)
        or len(point) != 2
        or any(type(n) is not int for n in point)
    ):
        raise TypeError("points must be (column, row) integer tuples")
    if not (0 <= point[0] < size[0] and 0 <= point[1] < size[1]):
        raise ValueError("points must lie inside size=(columns, rows)")
    return point


class _Accent:
    def __init__(
        self,
        *,
        size: tuple[int, int],
        duration: float,
        hold_duration: float,
        repeat: bool,
        repeat_delay: float,
        x: int | None,
        y: int | None,
        spacing: tuple[int, int],
        glyph: str,
    ) -> None:
        _size(size)
        _size(spacing)
        for name, value in (("x", x), ("y", y)):
            if value is not None and type(value) is not int:
                raise TypeError(f"{name} must be an integer or None")
        _seconds(duration, "duration")
        _seconds(hold_duration, "hold_duration")
        if duration == 0:
            raise ValueError("duration must be positive")
        self.size, self.spacing, self.x, self.y = size, spacing, x, y
        self.duration, self.hold_duration = duration, hold_duration
        self.repeat, self.repeat_delay = repeat, repeat_delay
        self.glyph = _glyph(glyph)
        self._clock = _CycleClock(duration + hold_duration, repeat, 0, repeat_delay)

    @property
    def progress(self) -> float:
        """Travel/expansion fraction from zero to one, excluding hold and gap."""
        return min(1.0, self._clock.time / self.duration)

    @property
    def finished(self) -> bool:
        """A one-shot finishes after duration + hold_duration and paints nothing."""
        return not self.repeat and self._clock.time >= self._clock.duration

    @property
    def visible(self) -> bool:
        return not self.finished and self._clock.visible

    def start(self) -> None:
        """Inert; repeated starts preserve time. No resources or input are owned."""

    def close(self) -> None:
        """Inert and idempotent, including before startup."""

    def update(self, dt: float) -> None:
        """Advance by non-negative simulation seconds, independently of draw FPS."""
        self._clock.update(dt)

    def draw(self, buffer: Buffer) -> None:
        """Paint without advancing time; centered placement follows the viewport."""
        if self.visible:
            grid = GridViewport(
                buffer, *self.size, x=self.x, y=self.y, spacing=self.spacing
            )
            self._paint(grid)

    def _paint(self, grid: GridViewport) -> None:
        raise NotImplementedError


class PathEffect(_Accent):
    """Move a pulse along supplied board cells or progressively trace the route.

    points are copied, ordered (column, row) cells inside size=(columns, rows).
    Each interval between entries takes equal time; no interpolation, pathfinding
    or solver consumption is performed. Repeated points create timed pauses.
    mode='pulse' paints the current cell plus up to trail preceding cells;
    mode='trace' paints all visited cells. trail counts cells, not seconds.

    duration is positive simulation seconds from first to last cell; a one-cell
    path stays there. hold_duration retains the final state before disappearing.
    repeat adds a blank repeat_delay and starts again. Empty paths finish at once.
    x/y=None center the board like GridViewport; spacing separates glyph anchors.
    Resize recenters without changing time. Unpainted cells are transparent.
    Layer supplies masks/style/background preservation. No resources or input
    are owned; start/close are inert, update advances time, and draw is pure.
    """

    def __init__(
        self,
        points: Sequence[Cell],
        *,
        size: tuple[int, int],
        duration: float = 2,
        mode: PathMode = "pulse",
        trail: int = 3,
        glyph: str = "*",
        hold_duration: float = 0,
        repeat: bool = False,
        repeat_delay: float = 1,
        x: int | None = None,
        y: int | None = None,
        spacing: tuple[int, int] = (1, 1),
    ) -> None:
        if mode not in ("pulse", "trace"):
            raise ValueError("mode must be 'pulse' or 'trace'")
        if type(trail) is not int:
            raise TypeError("trail must be an integer")
        if trail < 0:
            raise ValueError("trail must be non-negative")
        super().__init__(
            size=size,
            duration=duration,
            hold_duration=hold_duration,
            repeat=repeat,
            repeat_delay=repeat_delay,
            x=x,
            y=y,
            spacing=spacing,
            glyph=glyph,
        )
        self.points = tuple(_point(point, size) for point in points)
        self.mode, self.trail = mode, trail

    @property
    def finished(self) -> bool:
        return not self.points or super().finished

    @property
    def position(self) -> Cell | None:
        """Current board cell, or None when empty/finished/in a repeat gap."""
        return self.points[self._index] if self.visible else None

    @property
    def _index(self) -> int:
        return min(
            len(self.points) - 1, floor(self.progress * (len(self.points) - 1) + 1e-9)
        )

    def _paint(self, grid: GridViewport) -> None:
        first = 0 if self.mode == "trace" else max(0, self._index - self.trail)
        grid.path(self.points[first : self._index + 1], self.glyph)


class PulseEffect(_Accent):
    """Pulse a board marker through palette colors, then reveal lower layers.

    center is a board cell inside size. colors run dim-to-bright and back once
    per cycle; cycles is a positive integer within duration simulation seconds.
    This changes the marker's foreground, not terminal opacity. hold_duration
    holds its final dim color. See PathEffect for placement, repeat, resize,
    transparency and inert lifecycle contracts. Layer styling may override color.
    """

    def __init__(
        self,
        center: Cell,
        *,
        size: tuple[int, int],
        duration: float = 1,
        cycles: int = 2,
        colors: tuple[int, ...] = (238, 244, 250, 255),
        glyph: str = "*",
        hold_duration: float = 0,
        repeat: bool = False,
        repeat_delay: float = 1,
        x: int | None = None,
        y: int | None = None,
        spacing: tuple[int, int] = (1, 1),
    ) -> None:
        if type(cycles) is not int:
            raise TypeError("cycles must be an integer")
        if cycles < 1:
            raise ValueError("cycles must be positive")
        if not colors:
            raise ValueError("colors must not be empty")
        self._styles = tuple(TextStyle(foreground=color) for color in colors)
        if any(color is None for color in colors):
            raise TypeError("colors must contain palette integers")
        super().__init__(
            size=size,
            duration=duration,
            hold_duration=hold_duration,
            repeat=repeat,
            repeat_delay=repeat_delay,
            x=x,
            y=y,
            spacing=spacing,
            glyph=glyph,
        )
        self.center = _point(center, size)
        self.cycles, self.colors = cycles, tuple(colors)

    def _paint(self, grid: GridViewport) -> None:
        phase = (self.progress * self.cycles) % 1
        strength = 1 - abs(2 * phase - 1)
        index = min(len(self._styles) - 1, floor(strength * len(self._styles)))
        grid.put(*self.center, self._styles[index]._cell(self.glyph))


class RippleEffect(_Accent):
    """Expand a ring from a board cell, then reveal the underlying animation.

    radius and thickness are positive finite board-cell distances. metric chooses
    a circular, diamond, or square ring. The ring includes distances within half
    thickness of progress*radius; its initial frame includes the center.
    spacing=(2,1) often makes board circles look rounder in a terminal. Drawing
    visits only visible cell anchors, even for very large boards/radii.
    See PathEffect for timing, placement, repeat and inert lifecycle contracts.
    """

    def __init__(
        self,
        center: Cell,
        *,
        size: tuple[int, int],
        radius: float = 5,
        duration: float = 1,
        thickness: float = 1,
        metric: RippleMetric = "euclidean",
        glyph: str = "*",
        hold_duration: float = 0,
        repeat: bool = False,
        repeat_delay: float = 1,
        x: int | None = None,
        y: int | None = None,
        spacing: tuple[int, int] = (1, 1),
    ) -> None:
        for name, value in (("radius", radius), ("thickness", thickness)):
            _seconds(value, name)
            if value == 0:
                raise ValueError(f"{name} must be positive")
        if metric not in ("euclidean", "manhattan", "chebyshev"):
            raise ValueError("metric must be 'euclidean', 'manhattan', or 'chebyshev'")
        super().__init__(
            size=size,
            duration=duration,
            hold_duration=hold_duration,
            repeat=repeat,
            repeat_delay=repeat_delay,
            x=x,
            y=y,
            spacing=spacing,
            glyph=glyph,
        )
        self.center = _point(center, size)
        self.radius, self.thickness, self.metric = radius, thickness, metric

    def _paint(self, grid: GridViewport) -> None:
        left, top, right, bottom = grid._clip()
        sx, sy = grid.spacing
        first_x, first_y = (
            max(0, -((grid.x - left) // sx)),
            max(0, -((grid.y - top) // sy)),
        )
        last_x = min(grid.columns, (right - 1 - grid.x) // sx + 1)
        last_y = min(grid.rows, (bottom - 1 - grid.y) // sy + 1)
        for y in range(first_y, last_y):
            for x in range(first_x, last_x):
                dx, dy = abs(x - self.center[0]), abs(y - self.center[1])
                distance = (
                    hypot(dx, dy)
                    if self.metric == "euclidean"
                    else dx + dy
                    if self.metric == "manhattan"
                    else max(dx, dy)
                )
                if abs(distance - self.progress * self.radius) <= self.thickness / 2:
                    grid.put(x, y, self.glyph)
