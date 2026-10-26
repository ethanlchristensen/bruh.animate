"""Scrollable animation canvases and bounded, append-only text history."""

from __future__ import annotations

from bisect import bisect_right
from collections import deque
from typing import Literal

from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .grid import _glyph
from .keyboard import KeyBinding, KeyBindings, _set_visible
from .player import Animation
from .resize import _resize, _size
from .widgets import TextStyle, _validate_text

LogWrap = Literal["none", "character"]


def _offset(value: tuple[int, int]) -> None:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(type(n) is not int for n in value)
    ):
        raise TypeError("offset must be an (x, y) tuple of integers")


class _Scrolling:
    def __init__(self, size: tuple[int, int]) -> None:
        _size(size)
        self._size = size
        self._offset = (0, 0)
        self._content_size = (0, 0)
        self._started = self._closed = False
        self._bindings = KeyBindings(
            KeyBinding("up", lambda: self.scroll_by(dy=-1), description="scroll"),
            KeyBinding("down", lambda: self.scroll_by(dy=1)),
            KeyBinding("left", lambda: self.scroll_by(dx=-1)),
            KeyBinding("right", lambda: self.scroll_by(dx=1)),
            KeyBinding("page_up", self.page_up),
            KeyBinding("page_down", self.page_down),
            KeyBinding("home", self.home, description="top"),
            KeyBinding("end", self.end, description="bottom"),
        )

    @property
    def size(self) -> tuple[int, int]:
        """Viewport (width, height) in cells; change through resize()."""
        return self._size

    @property
    def content_size(self) -> tuple[int, int]:
        """Scrollable content (width, height), in cells/display rows."""
        return self._content_size

    @property
    def offset(self) -> tuple[int, int]:
        """Clamped top-left (column, display row), relative to content."""
        return self._offset

    @property
    def bindings(self) -> KeyBindings:
        """Arrow, Page Up/Down, Home/End bindings; no polling or quit defaults.

        Give these to FocusTarget, or pass bindings.handle_event to Player with
        your own quit routing. Actions only move the view, never update content.
        """
        return self._bindings

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("Views are single-use; construct a new instance")

    def _ready(self) -> None:
        self._open()
        if not self._started:
            raise RuntimeError("View must be started before update or draw")

    def _clamp(self) -> None:
        x, y = (
            min(max(0, self._offset[i]), max(0, self.content_size[i] - self.size[i]))
            for i in (0, 1)
        )
        self._offset = (x, y)

    def scroll_to(self, offset: tuple[int, int]) -> None:
        """Set an absolute cell offset; out-of-range coordinates clamp."""
        self._open()
        _offset(offset)
        self._offset = offset
        self._clamp()

    def scroll_by(self, *, dx: int = 0, dy: int = 0) -> None:
        """Move by signed columns/rows; positive means right/down."""
        _offset((dx, dy))
        self.scroll_to((self.offset[0] + dx, self.offset[1] + dy))

    def page_up(self) -> None:
        """Move up one viewport height, with a one-row overlap when possible."""
        self.scroll_by(dy=-max(1, self.size[1] - 1))

    def page_down(self) -> None:
        """Move down one viewport height, with a one-row overlap when possible."""
        self.scroll_by(dy=max(1, self.size[1] - 1))

    def home(self) -> None:
        """Move to the top-left of content."""
        self.scroll_to((0, 0))

    def end(self) -> None:
        """Move to the bottom, retaining the horizontal offset."""
        self.scroll_to((self.offset[0], max(0, self.content_size[1] - self.size[1])))


class ScrollView(_Scrolling):
    """Own an animation rendered on a larger canvas and show a clipped viewport.

    size and content_size are positive (width, height) in cells. Construction
    performs no lifecycle calls. Start notifies the child of content_size, then
    starts it; update forwards simulation seconds once. Draw only copies current
    content. Viewport resize clamps offset without resizing/restarting the child.
    set_content_size explicitly changes its canvas. Completion mirrors the child.

    None cells reveal background; background=None preserves lower layers. Plain
    spaces paint. Close is idempotent, including before start and after failures.
    Never share the child with another owner. Bindings are opt-in via FocusTarget
    or Player. Scrolling adds no clock, input poller, or terminal dependency.
    """

    def __init__(
        self,
        animation: Animation,
        *,
        size: tuple[int, int],
        content_size: tuple[int, int],
        background: str | None = " ",
    ) -> None:
        if not isinstance(animation, Animation):
            raise TypeError("animation must implement Animation")
        _size(content_size)
        if background is not None:
            _glyph(background)
        super().__init__(size)
        self._animation = animation
        self._content_size = content_size
        self._background = background
        self._canvas = Buffer(content_size[1], content_size[0])
        self._visible = True

    @property
    def animation(self) -> Animation:
        """Owned child; do not start, close, or re-own it separately."""
        return self._animation

    @property
    def finished(self) -> bool | None:
        return getattr(self.animation, "finished", None)

    def resize(self, size: tuple[int, int]) -> None:
        """Change viewport dimensions, preserving/clamping the cell offset."""
        self._open()
        _size(size)
        self._size = size
        self._clamp()

    def set_content_size(self, size: tuple[int, int]) -> None:
        """Resize the child canvas without advancing or restarting content."""
        self._open()
        _size(size)
        if size != self.content_size:
            if self._started:
                _resize(self.animation, size)
            self._canvas = Buffer(size[1], size[0])
            self._content_size = size
            self._clamp()

    def set_visible(self, visible: bool) -> None:
        """Propagate parent visibility; clipping alone does not infer focus."""
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        if not self._closed:
            self._visible = visible
            _set_visible(self.animation, visible)

    def start(self) -> None:
        self._open()
        if self._started:
            return
        try:
            _resize(self.animation, self.content_size)
            _set_visible(self.animation, self._visible)
            self.animation.start()
            self._started = True
        except BaseException:
            self.close()
            raise

    def update(self, dt: float) -> None:
        self._ready()
        _seconds(dt, "dt")
        self.animation.update(dt)

    def draw(self, buffer: Buffer) -> None:
        self._ready()
        if not self._visible:
            return
        self._canvas.clear_buffer(val=None)
        self.animation.draw(self._canvas)
        ox, oy = self.offset
        for y in range(min(self.size[1], buffer.height())):
            for x in range(min(self.size[0], buffer.width())):
                cell = self._background
                if y + oy < self.content_size[1] and x + ox < self.content_size[0]:
                    content = self._canvas.get_char(x + ox, y + oy)
                    if content is not None:
                        cell = content
                if cell is not None:
                    buffer.put_char(x, y, cell)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.animation.close()


class LogView(_Scrolling):
    """Bounded plain-text history with optional cell wrapping and tail following.

    append accepts newline-separated logical lines, including empty/trailing
    lines. max_lines bounds retained logical lines, not characters or wrapped
    rows; oldest lines are evicted. wrap='character' breaks at cell boundaries;
    'none' enables horizontal scrolling. Style is applied per cell, as with Label.

    Upward scrolling/Home suspends follow_tail. End or follow_tail=True resumes.
    Scrolling down to the bottom alone does not resume it. Append and resize
    preserve the top logical line/character when not following, or show the oldest
    remaining line if that anchor was evicted. Draw never changes scroll state.
    Append before start is supported. This single-use widget owns no resources;
    append from the player/application thread, not a background logging thread.
    """

    def __init__(
        self,
        *,
        size: tuple[int, int],
        max_lines: int = 1000,
        wrap: LogWrap = "character",
        follow_tail: bool = True,
        style: TextStyle | None = None,
        fill: bool = True,
    ) -> None:
        if type(max_lines) is not int:
            raise TypeError("max_lines must be an integer")
        if max_lines < 1:
            raise ValueError("max_lines must be positive")
        if wrap not in ("none", "character"):
            raise ValueError("wrap must be none or character")
        if type(follow_tail) is not bool or type(fill) is not bool:
            raise TypeError("follow_tail and fill must be bools")
        if style is not None and not isinstance(style, TextStyle):
            raise TypeError("style must be TextStyle or None")
        super().__init__(size)
        self._max_lines, self._wrap = max_lines, wrap
        self._follow_tail = follow_tail
        self._style, self._fill = style or TextStyle(), fill
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._first_line = 0
        self._starts = [0]
        self._reflow(None)
        self._bindings = KeyBindings(
            *(
                KeyBinding("end", self.end, description="follow")
                if binding.key == "end"
                else binding
                for binding in self._bindings.bindings
            )
        )

    @property
    def max_lines(self) -> int:
        """Maximum retained logical lines, before wrapping."""
        return self._max_lines

    @property
    def wrap(self) -> LogWrap:
        """Wrapping mode chosen at construction: none or character."""
        return self._wrap

    @property
    def lines(self) -> tuple[str, ...]:
        """Snapshot of retained logical lines, oldest first."""
        return tuple(self._lines)

    @property
    def line_count(self) -> int:
        """Number of retained logical lines; wrapped rows do not add to this."""
        return len(self._lines)

    @property
    def follow_tail(self) -> bool:
        """Whether append/resize keeps the bottom visible; enabling jumps there."""
        return self._follow_tail

    @follow_tail.setter
    def follow_tail(self, value: bool) -> None:
        self._open()
        if type(value) is not bool:
            raise TypeError("follow_tail must be a bool")
        self._follow_tail = value
        if value:
            self.end()

    @property
    def at_bottom(self) -> bool:
        """Whether the newest row is visible, independently of follow_tail."""
        return self.offset[1] == max(0, self.content_size[1] - self.size[1])

    def _anchor(self) -> tuple[int, int] | None:
        if not self._lines:
            return None
        index = bisect_right(self._starts, self.offset[1]) - 1
        character = (
            (self.offset[1] - self._starts[index]) * self.size[0]
            if self.wrap == "character"
            else 0
        )
        return self._first_line + index, character

    def _reflow(self, anchor: tuple[int, int] | None) -> None:
        width = self.size[0]
        starts = [0]
        longest = 0
        for line in self._lines:
            longest = max(longest, len(line))
            starts.append(
                starts[-1]
                + (
                    max(1, (len(line) + width - 1) // width)
                    if self.wrap == "character"
                    else 1
                )
            )
        self._starts = starts
        self._content_size = (
            width if self.wrap == "character" else longest,
            starts[-1],
        )
        if self.follow_tail:
            y = max(0, starts[-1] - self.size[1])
        elif anchor is not None and self._lines:
            index = max(0, min(len(self._lines) - 1, anchor[0] - self._first_line))
            character = anchor[1] if anchor[0] == self._first_line + index else 0
            y = starts[index] + (character // width if self.wrap == "character" else 0)
        else:
            y = 0
        self._offset = (self.offset[0], y)
        self._clamp()

    def append(self, text: str) -> None:
        """Append validated plain text, evicting oldest excess logical lines."""
        self._open()
        _validate_text(text, multiline=True)
        anchor = self._anchor()
        lines = text.split("\n")
        self._first_line += max(0, len(self._lines) + len(lines) - self.max_lines)
        self._lines.extend(lines)
        self._reflow(anchor)

    def clear(self) -> None:
        """Discard history and reset offsets, retaining the follow setting."""
        self._open()
        self._first_line += len(self._lines)
        self._lines.clear()
        self._offset = (0, 0)
        self._reflow(None)

    def resize(self, size: tuple[int, int]) -> None:
        """Rewrap for a new viewport, preserving the reading anchor or tail."""
        self._open()
        _size(size)
        anchor = self._anchor()
        self._size = size
        self._reflow(anchor)

    def scroll_to(self, offset: tuple[int, int]) -> None:
        """Clamp to an absolute cell offset; upward requests suspend following."""
        self._open()
        _offset(offset)
        if offset[1] < self.offset[1]:
            self._follow_tail = False
        super().scroll_to(offset)

    def home(self) -> None:
        """Show the oldest retained line and suspend following."""
        self._open()
        self._follow_tail = False
        super().home()

    def end(self) -> None:
        """Show the newest row and resume following; keep horizontal offset."""
        self._open()
        self._follow_tail = True
        super().end()

    def start(self) -> None:
        self._open()
        self._started = True

    def update(self, dt: float) -> None:
        self._ready()
        _seconds(dt, "dt")

    def draw(self, buffer: Buffer) -> None:
        self._ready()
        width, height = (
            min(self.size[0], buffer.width()),
            min(self.size[1], buffer.height()),
        )
        if self._fill:
            blank = self._style._cell(" ")
            for y in range(height):
                for x in range(width):
                    buffer.put_char(x, y, blank)
        ox, oy = self.offset
        for y in range(min(height, self.content_size[1] - oy)):
            index = bisect_right(self._starts, oy + y) - 1
            start = (
                (oy + y - self._starts[index]) * self.size[0]
                if self.wrap == "character"
                else ox
            )
            text = self._lines[index][start : start + width]
            for x, char in enumerate(text):
                buffer.put_char(x, y, self._style._cell(char))

    def close(self) -> None:
        self._closed = True
