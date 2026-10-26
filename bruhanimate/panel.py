"""Owned local animation surfaces with positioning, framing, and motion."""

from __future__ import annotations

from collections.abc import Callable
from math import floor, isfinite

from ._validation import _seconds
from .bruheffect.base_effect import BaseEffect
from .bruhutil.bruhffer import Buffer
from .grid import _glyph
from .keyboard import FocusTarget, _set_visible
from .player import Animation
from .resize import _resize, _size
from .scene import Layer, Scene


def _pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{name} must be an (x, y) tuple")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"{name} coordinates must be numbers")
        if not isfinite(item):
            raise ValueError(f"{name} coordinates must be finite")
    return float(value[0]), float(value[1])


class Panel:
    """Own an animation in a movable, clipped local content area.

    ``size=(width, height)`` is the positive content size, excluding the border.
    Supply exactly one of ``animation`` or ``effect_factory``. The factory runs
    once at start with a fresh content-sized Buffer; built-in effect buffers
    must match size. Construction is inert. The panel owns the child, closes it
    on cleanup/failed startup, and is single-use after close. Never share a child
    between owners. A supplied child is also closed if the panel never starts.

    ``position`` is the outer top-left in parent coordinates. ``velocity`` is
    columns/second and rows/second. Motion advances only in update(dt). Bounds
    are an optional parent-coordinate (x, y, width, height) clip. ``bounce=True``
    requires bounds, reflects motion at their edges, and clamps the initial
    position inside them. An oversized axis stays at the corresponding origin.
    Bounds never resize the child. Scene order determines stacking.

    Border uses ASCII geometry; title is plain single-cell text, clipped to the
    top edge, and requires border=True. Optional border colors are ANSI palette
    indices 0..255. Background is one optionally SGR-styled cell, or None for
    transparency. Child spaces paint; child None cells reveal the background.

    ``updates_per_second`` paces only the child via Layer; None forwards every
    update. ``max_catch_up`` has Layer's discard-on-cap behavior. Motion still
    uses all supplied dt. Completion mirrors the child; input is not forwarded.
    Pass handlers to Player explicitly. fit=True follows parent resize notifications;
    the default keeps fixed geometry. focus attaches one FocusTarget for keyboard
    routing through FocusGroup.handle_event. Its border becomes bold with
    focus_border_color (None retains its normal color). Drag handling is deferred.
    """

    def __init__(
        self,
        animation: Animation | None = None,
        *,
        size: tuple[int, int],
        effect_factory: Callable[[Buffer], Animation] | None = None,
        position: tuple[float, float] = (0, 0),
        velocity: tuple[float, float] = (0, 0),
        bounds: tuple[int, int, int, int] | None = None,
        bounce: bool = False,
        border: bool = True,
        fit: bool = False,
        focus: FocusTarget | None = None,
        focus_border_color: int | None = 226,
        title: str = "",
        border_color: int | None = None,
        border_background: int | None = None,
        background: str | None = " ",
        updates_per_second: float | None = None,
        max_catch_up: int = 5,
    ) -> None:
        if (animation is None) == (effect_factory is None):
            raise ValueError("Supply exactly one of animation or effect_factory")
        if animation is not None and not isinstance(animation, Animation):
            raise TypeError("Panel animation must implement Animation")
        if effect_factory is not None and not callable(effect_factory):
            raise TypeError("effect_factory must be callable")
        if (
            not isinstance(size, tuple)
            or len(size) != 2
            or any(type(n) is not int for n in size)
        ):
            raise TypeError("size must be a (width, height) tuple of integers")
        if any(n < 1 for n in size):
            raise ValueError("Panel content dimensions must be positive")
        if focus is not None and not isinstance(focus, FocusTarget):
            raise TypeError("focus must be a FocusTarget or None")
        if type(fit) is not bool:
            raise TypeError("fit must be a bool")
        if type(border) is not bool or type(bounce) is not bool:
            raise TypeError("border and bounce must be bools")
        if bounds is not None:
            if (
                not isinstance(bounds, tuple)
                or len(bounds) != 4
                or any(type(n) is not int for n in bounds)
            ):
                raise TypeError(
                    "bounds must be an (x, y, width, height) tuple of integers"
                )
            if bounds[2] < 0 or bounds[3] < 0:
                raise ValueError("bounds dimensions must be non-negative")
        if bounce and bounds is None:
            raise ValueError("bounce=True requires explicit bounds")
        if not isinstance(title, str):
            raise TypeError("title must be a string")
        if title and not border:
            raise ValueError("A title requires border=True")
        for character in title:
            try:
                _glyph(character)
            except ValueError as error:
                raise ValueError("title must contain plain single-cell text") from error
        for name, color in (
            ("border_color", border_color),
            ("border_background", border_background),
            ("focus_border_color", focus_border_color),
        ):
            if color is not None:
                if type(color) is not int:
                    raise TypeError(f"{name} must be an integer or None")
                if not 0 <= color <= 255:
                    raise ValueError(f"{name} must be between 0 and 255")
        if background is not None:
            _glyph(background)
        if updates_per_second is not None:
            _seconds(updates_per_second, "updates_per_second")
            if updates_per_second == 0:
                raise ValueError("updates_per_second must be positive")
        if type(max_catch_up) is not int:
            raise TypeError("max_catch_up must be an integer")
        if max_catch_up < 1:
            raise ValueError("max_catch_up must be positive")
        self._focus, self._focus_color = focus, focus_border_color
        self._visible = True
        self._fit = fit
        self._size = size
        self._phase = _pair(position, "position")
        self._velocity = _pair(velocity, "velocity")
        self._bounds, self._bounce, self._border = bounds, bounce, border
        self._title, self._background = title, background
        self._rate, self._max_catch_up = updates_per_second, max_catch_up
        self._factory, self._animation = effect_factory, animation
        self._scene: Scene | None = None
        self._canvas = Buffer(size[1], size[0])
        self._started = self._closed = False
        colors = []
        if border_color is not None:
            colors.append(f"38;5;{border_color}")
        if border_background is not None:
            colors.append(f"48;5;{border_background}")
        self._border_style = f"\x1b[{';'.join(colors)}m" if colors else ""
        self._check_buffer(animation)
        if bounce and bounds is not None:
            self._phase = (
                min(
                    max(self._phase[0] - bounds[0], 0.0),
                    max(0, bounds[2] - self.outer_size[0]),
                ),
                min(
                    max(self._phase[1] - bounds[1], 0.0),
                    max(0, bounds[3] - self.outer_size[1]),
                ),
            )

        if focus is not None:
            focus._attach(self)

    def set_visible(self, visible: bool) -> None:
        """Set painting/focus availability without pausing or closing content.

        Layouts propagate empty-slot and ancestor visibility automatically.
        This does not infer occlusion or test moving panels against screen edges.
        """
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        if self._closed:
            return
        self._visible = visible
        if self._focus is not None:
            self._focus._activate(visible and self._started and not self._closed)
        if self._animation is not None:
            _set_visible(self._animation, visible)

    def move_to(self, position: tuple[float, float]) -> None:
        """Move the outer origin without advancing content; bounce panels clamp it."""
        phase = _pair(position, "position")
        if self._bounce and self._bounds is not None:
            x, y = (
                min(
                    max(phase[i] - self._bounds[i], 0.0),
                    max(0, self._bounds[i + 2] - self.outer_size[i]),
                )
                for i in (0, 1)
            )
            phase = x, y
        self._phase = phase

    def resize(self, size: tuple[int, int]) -> None:
        """Receive parent (width, height); fit=True fills it, excluding borders.

        Fixed panels retain geometry. Fitting panels retain their child and
        clocks. A border in a viewport smaller than three cells is clipped;
        the private content keeps at least one cell on each axis. Bounds remain
        explicit parent-coordinate clips and are not changed by notifications.
        """
        _size(size)
        if self._closed:
            raise RuntimeError("Cannot resize a closed Panel")
        if not self._fit:
            return
        inset = 2 * self._border
        content_size = (max(1, size[0] - inset), max(1, size[1] - inset))
        if content_size == self._size:
            return
        if self._animation is not None:
            _resize(self._animation, content_size)
        self._size = content_size
        self._canvas = Buffer(content_size[1], content_size[0])

    def _check_buffer(self, animation: Animation | None) -> None:
        if (
            isinstance(animation, BaseEffect)
            and (
                animation._viewport
                or (animation.buffer.width(), animation.buffer.height())
            )
            != self.size
        ):
            raise ValueError("Panel size must match the effect's buffer dimensions")

    @property
    def size(self) -> tuple[int, int]:
        """Content (width, height), excluding the optional border."""
        return self._size

    @property
    def outer_size(self) -> tuple[int, int]:
        """Full footprint (width, height), including the optional border."""
        inset = 2 if self._border else 0
        return self.size[0] + inset, self.size[1] + inset

    @property
    def velocity(self) -> tuple[float, float]:
        """Configured motion in columns/second and rows/second, before reflection."""
        return self._velocity

    @property
    def position(self) -> tuple[float, float]:
        """Current outer top-left in parent coordinates; drawing floors to cells."""
        if not self._bounce or self._bounds is None:
            return self._phase
        bx, by, bw, bh = self._bounds
        width, height = self.outer_size

        def reflect(phase: float, origin: int, limit: int) -> float:
            return (
                float(origin)
                if limit <= 0
                else origin + limit - abs(limit - phase % (2 * limit))
            )

        return reflect(self._phase[0], bx, bw - width), reflect(
            self._phase[1], by, bh - height
        )

    @property
    def animation(self) -> Animation | None:
        """Owned child; None until startup when using effect_factory. Do not re-own it."""
        return self._animation

    @property
    def finished(self) -> bool | None:
        """Child completion; None for endless content or an uncalled factory."""
        return getattr(self._animation, "finished", None)

    def start(self) -> None:
        """Create/acquire the child once, closing it if startup fails."""
        if self._closed:
            raise RuntimeError("Panel is single-use; construct a new instance")
        if self._started:
            return
        self._started = True
        try:
            if self._factory is not None:
                child = self._factory(Buffer(self.size[1], self.size[0]))
                if not isinstance(child, Animation):
                    raise TypeError("effect_factory must return an Animation")
                self._animation = child
            assert self._animation is not None
            self._check_buffer(self._animation)
            _set_visible(self._animation, self._visible)
            self._scene = Scene(
                Layer(
                    self._animation,
                    updates_per_second=self._rate,
                    max_catch_up=self._max_catch_up,
                )
            )
            self._scene.start()
            if self._focus is not None:
                self._focus._activate(self._visible)
        except BaseException:
            self.close()
            raise

    def update(self, dt: float) -> None:
        """Advance motion by simulation seconds and pace the child independently."""
        if self._scene is None or self._closed:
            raise RuntimeError("Panel must be started and not closed before update")
        _seconds(dt, "dt")
        px, py = (self._phase[i] + self.velocity[i] * dt for i in (0, 1))
        if not isfinite(px) or not isfinite(py):
            raise ValueError("Panel motion exceeds finite coordinates")
        self._scene.update(dt)
        if self._bounce and self._bounds is not None:
            lx = self._bounds[2] - self.outer_size[0]
            ly = self._bounds[3] - self.outer_size[1]
            px = px % (2 * lx) if lx > 0 else 0.0
            py = py % (2 * ly) if ly > 0 else 0.0
        self._phase = px, py

    def draw(self, buffer: Buffer) -> None:
        """Translate current local pixels into a clipped parent area, without updates."""
        if self._scene is None or self._closed:
            raise RuntimeError("Panel must be started and not closed before draw")
        if not self._visible:
            return
        self._canvas.clear_buffer(val=self._background)
        self._scene.draw(self._canvas)
        x, y = (floor(value + 1e-9) for value in self.position)
        width, height = self.outer_size
        bx, by, bw, bh = self._bounds or (0, 0, buffer.width(), buffer.height())
        left, top = max(x, bx, 0), max(y, by, 0)
        right, bottom = (
            min(x + width, bx + bw, buffer.width()),
            min(y + height, by + bh, buffer.height()),
        )
        inset = int(self._border)
        title = (f" {self._title} " if self._title else "")[: self.size[0]].ljust(
            self.size[0], "-"
        )
        for dy in range(top, bottom):
            row = dy - y
            for dx in range(left, right):
                column = dx - x
                if self._border and (
                    row in (0, height - 1) or column in (0, width - 1)
                ):
                    if column in (0, width - 1):
                        cell = "+" if row in (0, height - 1) else "|"
                    else:
                        cell = title[column - 1] if row == 0 else "-"
                    style = self._border_style
                    if self._focus is not None and self._focus.focused:
                        style += "\x1b[1m"
                        if self._focus_color is not None:
                            style += f"\x1b[38;5;{self._focus_color}m"
                    if style:
                        cell = f"{style}{cell}\x1b[0m"
                else:
                    cell = self._canvas.buffer[row - inset][column - inset]
                if cell is not None:
                    buffer.put_char(dx, dy, str(cell))

    def close(self) -> None:
        """Release owned content once, including before start and after failures."""
        if self._closed:
            return
        self._closed = True
        if self._focus is not None:
            self._focus._detach()
        if self._scene is not None:
            self._scene.close()
        elif self._animation is not None:
            self._animation.close()
