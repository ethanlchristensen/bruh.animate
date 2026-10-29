"""Composition independent of terminal ownership, pacing, and presentation."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from math import floor, isfinite

from ._clock import _fixed_steps
from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .grid import _glyph
from .keyboard import _set_visible
from .masks import CellMask
from .player import Animation
from .resize import _resize, _size
from .styling import TextStyle, _style_cell


@dataclass(frozen=True)
class Layer:
    """One animation in paint order. None cells always reveal lower layers.

    transparent=True also treats plain spaces as transparent. ANSI-colored
    spaces remain visible, so colored backgrounds can be composed deliberately.

    region=(x, y, width, height) clips painting in destination coordinates;
    it does not translate or resize the child's full-scene drawing buffer.
    Negative origins and empty regions are allowed. Clipping never pauses updates.
    updates_per_second=None forwards every Scene update unchanged. A positive
    rate accumulates supplied dt and sends fixed 1/rate ticks, beginning after
    one full interval. max_catch_up bounds ticks per Scene update; reaching the
    bound discards remaining accumulated time. Presentation still draws current
    state every frame. These clocks use simulation seconds, not wall time.

    mask(x, y, (width, height)) is a pure destination-coordinate predicate;
    False clips the cell without changing updates or child ownership. ImageMask
    builds one from ASCII rows. style overrides cell colors/bold using TextStyle.
    preserve_background=True retains the already composed lower cell's background
    unless style.background explicitly overrides it. These options work with any
    Animation. Spaces remain opaque unless transparent=True, before styling.
    """

    animation: Animation
    transparent: bool = False
    region: tuple[int, int, int, int] | None = field(default=None, kw_only=True)
    updates_per_second: float | None = field(default=None, kw_only=True)
    max_catch_up: int = field(default=5, kw_only=True)
    mask: CellMask | None = field(default=None, kw_only=True)
    style: TextStyle | None = field(default=None, kw_only=True)
    preserve_background: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        if self.mask is not None and not callable(self.mask):
            raise TypeError("mask must be a CellMask callable or None")
        if self.style is not None and not isinstance(self.style, TextStyle):
            raise TypeError("style must be a TextStyle or None")
        if type(self.preserve_background) is not bool:
            raise TypeError("preserve_background must be a bool")
        if type(self.transparent) is not bool:
            raise TypeError("transparent must be a bool")
        if self.region is not None:
            if not isinstance(self.region, tuple) or len(self.region) != 4:
                raise TypeError("region must be an (x, y, width, height) tuple")
            if any(type(value) is not int for value in self.region):
                raise TypeError("region coordinates and sizes must be integers")
            if self.region[2] < 0 or self.region[3] < 0:
                raise ValueError("region width and height must be non-negative")
        if self.updates_per_second is not None:
            _seconds(self.updates_per_second, "updates_per_second")
            if self.updates_per_second == 0:
                raise ValueError("updates_per_second must be positive")
        if type(self.max_catch_up) is not int:
            raise TypeError("max_catch_up must be an integer")
        if self.max_catch_up < 1:
            raise ValueError("max_catch_up must be positive")


class Scene:
    """Own and paint animations from back to front through the shared Player.

    Each child gets an isolated drawing buffer. A scene owns each child once;
    close runs in reverse start order, including after partial startup failure.
    Build a new scene to change its membership during playback.
    """

    def __init__(self, *layers: Animation | Layer):
        self.layers = tuple(
            layer if isinstance(layer, Layer) else Layer(layer) for layer in layers
        )
        children = [layer.animation for layer in self.layers]
        if any(not isinstance(child, Animation) for child in children):
            raise TypeError("Scene children must implement Animation")
        if len({id(child) for child in children}) != len(children):
            raise ValueError("A Scene cannot own the same animation twice")
        self._cleanup: ExitStack | None = None
        self._scratch: Buffer | None = None
        self._elapsed = [0.0] * len(self.layers)

    @property
    def finished(self) -> bool | None:
        """Finish when all finite children finish, ignoring endless backgrounds.

        A finite child exposes a boolean finished property. A scene containing
        only endless content reports None. Nested scenes use the same rule.
        """
        statuses = [getattr(layer.animation, "finished", None) for layer in self.layers]
        finite = [status for status in statuses if status is not None]
        return all(finite) if finite else None

    def start(self) -> None:
        if self._cleanup is not None:
            return
        self._cleanup = ExitStack()
        self._elapsed = [0.0] * len(self.layers)
        try:
            for layer in self.layers:
                self._cleanup.callback(layer.animation.close)
                layer.animation.start()
        except BaseException:
            self.close()
            raise

    def update(self, dt: float) -> None:
        """Advance layer clocks in seconds; no terminal polling or sleeping."""
        _seconds(dt, "dt")
        for index, layer in enumerate(self.layers):
            if layer.updates_per_second is None:
                layer.animation.update(dt)
                continue
            interval = 1 / layer.updates_per_second
            count, elapsed = _fixed_steps(
                self._elapsed[index], dt, interval, layer.max_catch_up
            )
            for _ in range(count):
                layer.animation.update(interval)
            self._elapsed[index] = elapsed

    def set_visible(self, visible: bool) -> None:
        """Propagate a parent's visibility to focusable descendants."""
        for layer in self.layers:
            _set_visible(layer.animation, visible)

    def resize(self, size: tuple[int, int]) -> None:
        """Notify children without changing layer clocks or fixed region clips."""
        _size(size)
        for layer in self.layers:
            _resize(layer.animation, size)
        self._scratch = None

    def draw(self, buffer: Buffer) -> None:
        size = (buffer.height(), buffer.width())
        if (
            self._scratch is None
            or (self._scratch.height(), self._scratch.width()) != size
        ):
            self._scratch = Buffer(*size)
        empty_row = [None] * size[1]
        for layer in self.layers:
            x, y, width, height = layer.region or (0, 0, size[1], size[0])
            left, top = max(0, x), max(0, y)
            right, bottom = min(size[1], x + width), min(size[0], y + height)
            if right <= left or bottom <= top:
                continue
            self._scratch.clear_buffer(val=None)
            layer.animation.draw(self._scratch)
            for y in range(top, bottom):
                source = self._scratch.buffer[y]
                # List equality skips empty rows in C, particularly valuable for
                # small panels on a large viewport. Custom draws remain isolated.
                if source == empty_row:
                    continue
                destination = buffer.buffer[y]
                for x in range(left, right):
                    cell = source[x]
                    if cell is not None:
                        value = str(cell)
                        if not (layer.transparent and value == " "):
                            if layer.mask is not None and not layer.mask(
                                x, y, (size[1], size[0])
                            ):
                                continue
                            if layer.style is not None or layer.preserve_background:
                                value = _style_cell(
                                    value,
                                    destination[x],
                                    layer.style,
                                    layer.preserve_background,
                                )
                            destination[x] = value

    def close(self) -> None:
        cleanup, self._cleanup = self._cleanup, None
        if cleanup is not None:
            cleanup.close()


class TimedOverlay:
    """Own an animation visible for duration seconds after an optional delay.

    Time advances only in update(dt), including when a sibling Playback is paused.
    The child starts when the delay elapses and closes on expiry or owner cleanup.
    duration=0 never starts it. Active time is [delay, delay + duration); a large
    update that skips this entire window never starts the child. Draw is read-only
    and paints nothing outside the window, revealing freshly composed lower layers.

    Child updates receive only the active part of dt. The child may finish early;
    its last state remains eligible for drawing until the duration expires. This
    wrapper reports finished on expiry and participates in Scene completion.
    It is single-use and does not forward input: route events explicitly through
    Player. Never give its child to another lifecycle owner.
    """

    def __init__(self, animation: Animation, *, duration: float, delay: float = 0):
        if not isinstance(animation, Animation):
            raise TypeError("TimedOverlay requires an Animation")
        _seconds(duration, "duration")
        _seconds(delay, "delay")
        if not isfinite(delay + duration):
            raise ValueError("delay + duration must be finite")
        self.animation = animation
        self.duration = duration
        self.delay = delay
        self._elapsed = 0.0
        self._started = False
        self._closed = False
        self._finished = duration == 0
        self._cleanup: ExitStack | None = None

    @property
    def finished(self) -> bool:
        """Whether the visibility window has expired; early close is not expiry."""
        return self._finished

    def _activate(self) -> None:
        self._cleanup = ExitStack()
        self._cleanup.callback(self.animation.close)
        try:
            self.animation.start()
        except BaseException:
            self.close()
            raise

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("TimedOverlay is single-use; construct a new instance")
        if self._started:
            return
        self._started = True
        if self.delay == 0 and not self.finished:
            self._activate()

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError(
                "TimedOverlay must be started and not closed before update"
            )
        _seconds(dt, "dt")
        if self.finished:
            return
        before = self._elapsed
        self._elapsed += dt
        end = self.delay + self.duration
        tolerance = min(1e-9, self.duration * 1e-6)
        if (
            self._cleanup is None
            and self._elapsed + tolerance < end
            and self._elapsed + tolerance >= self.delay
        ):
            self._activate()
        if self._cleanup is not None:
            active_dt = max(0.0, min(self._elapsed, end) - max(before, self.delay))
            if active_dt > 0 or dt == 0:
                self.animation.update(active_dt)
        if self._elapsed + tolerance >= end:
            self._finished = True
            cleanup, self._cleanup = self._cleanup, None
            if cleanup is not None:
                cleanup.close()

    def set_visible(self, visible: bool) -> None:
        """Propagate parent visibility without changing the visibility timer."""
        _set_visible(self.animation, visible)

    def resize(self, size: tuple[int, int]) -> None:
        """Notify unexpired content without resetting the visibility window."""
        _size(size)
        if not self._closed and not self.finished:
            _resize(self.animation, size)

    def draw(self, buffer: Buffer) -> None:
        if self._cleanup is not None and not self._closed:
            self.animation.draw(buffer)

    def close(self) -> None:
        self._closed = True
        cleanup, self._cleanup = self._cleanup, None
        if cleanup is not None:
            cleanup.close()


class ImageEffect:
    """Draw text or ASCII image rows, centered unless x/y are supplied.

    velocity is (columns/second, rows/second). Movement happens in update(),
    and out-of-bounds content is clipped. Spaces paint; use Layer transparency
    to reveal an animated background through them.

    characters_per_second enables a row-by-row reveal of non-space glyphs.
    It must be positive and finite; None displays the whole image immediately.
    Revealing starts blank, leaves spaces/unrevealed cells transparent, and
    advances only in update(dt), in simulation seconds. finished becomes True
    after the last glyph; the image remains visible and movement continues.
    With no reveal, finished is None. Use on_complete="hold" to keep a Scene's
    background running after reveal completion. Resize/repeated start do not
    reset progress. Rows must contain plain single-cell text, not ANSI escapes.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        velocity: tuple[float, float] = (0, 0),
        characters_per_second: float | None = None,
    ):
        if characters_per_second is not None:
            _seconds(characters_per_second, "characters_per_second")
            if characters_per_second == 0:
                raise ValueError("characters_per_second must be positive")
        self.rows = tuple(image.splitlines() if isinstance(image, str) else image)
        self.width = max(map(len, self.rows), default=0)
        self.x, self.y = x, y
        self.velocity = velocity
        self._offset_x = self._offset_y = 0.0
        self.characters_per_second = characters_per_second
        self._glyphs = (
            tuple(
                (column, row, _glyph(char))
                for row, text in enumerate(self.rows)
                for column, char in enumerate(text)
                if char != " "
            )
            if characters_per_second is not None
            else ()
        )
        self._revealed = 0.0

    @property
    def finished(self) -> bool | None:
        """Whether all reveal glyphs are visible; None for an immediate image."""
        if self.characters_per_second is None:
            return None
        return self._visible_count == len(self._glyphs)

    @property
    def _visible_count(self) -> int:
        return min(len(self._glyphs), floor(self._revealed + 1e-9))

    def start(self) -> None:
        pass

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        self._offset_x += self.velocity[0] * dt
        self._offset_y += self.velocity[1] * dt
        if self.characters_per_second is not None:
            self._revealed = min(
                len(self._glyphs), self._revealed + dt * self.characters_per_second
            )

    def draw(self, buffer: Buffer) -> None:
        x = (buffer.width() - self.width) // 2 if self.x is None else self.x
        y = (buffer.height() - len(self.rows)) // 2 if self.y is None else self.y
        if self.characters_per_second is not None:
            for column, row, char in self._glyphs[: self._visible_count]:
                buffer.put_char(
                    floor(x + self._offset_x) + column,
                    floor(y + self._offset_y) + row,
                    char,
                )
            return
        for row, text in enumerate(self.rows):
            buffer.put_at(
                floor(x + self._offset_x), floor(y + self._offset_y) + row, text
            )

    def close(self) -> None:
        pass
