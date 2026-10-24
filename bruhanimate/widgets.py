"""Single-cell text widgets that snapshot dynamic text during simulation updates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from .bruhutil.bruhffer import Buffer
from .grid import _glyph
from .scene import _seconds
from .styling import TextStyle as TextStyle

TextSource = str | Callable[[], str]
TextAlign = Literal["left", "center", "right"]
VerticalAlign = Literal["top", "middle", "bottom"]
TextOverflow = Literal["clip", "ellipsis", "wrap"]


def _validate_text(value: str, *, multiline: bool) -> str:
    if not isinstance(value, str):
        raise TypeError("Text sources must return strings")
    for char in value:
        if char == "\n" and multiline:
            continue
        try:
            _glyph(char)
        except ValueError as error:
            raise ValueError(
                "Text must use plain single-cell characters; style with TextStyle"
            ) from error
    return value


def _source(value: TextSource, *, multiline: bool) -> TextSource:
    if isinstance(value, str):
        _validate_text(value, multiline=multiline)
    elif not callable(value):
        raise TypeError("Text must be a string or a zero-argument string callback")
    return value


def _read(source: TextSource, *, multiline: bool) -> str:
    return _validate_text(source() if callable(source) else source, multiline=multiline)


def _clip(text: str, width: int, ellipsis: bool = False) -> str:
    if len(text) <= width:
        return text
    if ellipsis:
        return text[: max(0, width - 3)] + "." * min(3, width)
    return text[:width]


class Label:
    """Aligned plain text, optionally supplied by a live zero-argument callback.

    Text is validated/cached on start and once per update, never during draw.
    Static text is available immediately; dynamic text starts empty. Newlines
    are allowed, but controls, wide/combining glyphs and inline ANSI are not.
    wrap breaks at cell boundaries, not words. ellipsis shortens each long line
    with ASCII dots. Extra rows clip. fill=True paints the full local buffer
    with styled spaces; False leaves unpainted cells untouched. Text spaces paint.
    Widgets own no input or external resources. Callbacks should only read state.
    """

    def __init__(
        self,
        text: TextSource,
        *,
        align: TextAlign = "left",
        vertical_align: VerticalAlign = "top",
        overflow: TextOverflow = "clip",
        style: TextStyle | None = None,
        fill: bool = True,
    ) -> None:
        self._source = _source(text, multiline=True)
        if align not in ("left", "center", "right"):
            raise ValueError("align must be left, center, or right")
        if vertical_align not in ("top", "middle", "bottom"):
            raise ValueError("vertical_align must be top, middle, or bottom")
        if overflow not in ("clip", "ellipsis", "wrap"):
            raise ValueError("overflow must be clip, ellipsis, or wrap")
        if style is not None and not isinstance(style, TextStyle):
            raise TypeError("style must be a TextStyle or None")
        if type(fill) is not bool:
            raise TypeError("fill must be a bool")
        self._align, self._vertical, self._overflow = align, vertical_align, overflow
        self._style, self._fill = style or TextStyle(), fill
        self._text = text if isinstance(text, str) else ""
        self._started = False

    @property
    def text(self) -> str:
        """Most recently cached text; reading this never calls the source."""
        return self._text

    def start(self) -> None:
        if not self._started:
            self._text = _read(self._source, multiline=True)
            self._started = True

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started:
            raise RuntimeError("Label must be started before update")
        if callable(self._source):
            self._text = _read(self._source, multiline=True)

    def draw(self, buffer: Buffer) -> None:
        width, height = buffer.width(), buffer.height()
        if self._fill:
            buffer.clear_buffer(val=self._style._cell(" "))
        if width == 0 or height == 0:
            return
        rows: list[str] = []
        for line in self.text.split("\n", height):
            if self._overflow == "wrap":
                rows.extend(
                    line[i : i + width]
                    for i in range(
                        0, min(len(line), width * (height - len(rows))), width
                    )
                )
                if not line:
                    rows.append("")
            else:
                rows.append(_clip(line, width, self._overflow == "ellipsis"))
            if len(rows) >= height:
                break
        rows = rows[:height]
        y = {
            "top": 0,
            "middle": (height - len(rows)) // 2,
            "bottom": height - len(rows),
        }[self._vertical]
        for row, text in enumerate(rows):
            x = {
                "left": 0,
                "center": (width - len(text)) // 2,
                "right": width - len(text),
            }[self._align]
            for column, char in enumerate(text):
                buffer.put_char(x + column, y + row, self._style._cell(char))

    def close(self) -> None:
        self._started = False


class StatusBar:
    """One row of left/center/right text, refreshed at start and on each update.

    Sections are single-line TextSources, styled per cell. Draw never evaluates
    callbacks. The right section has first claim on space, then left, then center.
    Sections clip from their ends and leave a one-cell gap when space permits;
    they never overwrite one another. Only the first local row is painted.
    Use Slot(status, size=Fixed(1)) in a Column. No input routing is installed.
    """

    def __init__(
        self,
        left: TextSource = "",
        *,
        center: TextSource = "",
        right: TextSource = "",
        style: TextStyle | None = None,
    ) -> None:
        self._sources = tuple(
            _source(text, multiline=False) for text in (left, center, right)
        )
        if style is not None and not isinstance(style, TextStyle):
            raise TypeError("style must be a TextStyle or None")
        self._style = style or TextStyle()
        self._texts = tuple(
            text if isinstance(text, str) else "" for text in self._sources
        )
        self._started = False

    def _refresh(self) -> None:
        self._texts = tuple(_read(source, multiline=False) for source in self._sources)

    def start(self) -> None:
        if not self._started:
            self._refresh()
            self._started = True

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started:
            raise RuntimeError("StatusBar must be started before update")
        self._refresh()

    def draw(self, buffer: Buffer) -> None:
        width = buffer.width()
        if width == 0 or buffer.height() == 0:
            return
        for x in range(width):
            buffer.put_char(x, 0, self._style._cell(" "))
        left, center, right = self._texts
        right = _clip(right, width)
        rx = width - len(right)
        left = _clip(left, max(0, rx - int(bool(right))))
        start = len(left) + int(bool(left))
        end = rx - int(bool(right))
        center = _clip(center, max(0, end - start))
        cx = max(start, min((width - len(center)) // 2, end - len(center)))
        for x, text in ((0, left), (cx, center), (rx, right)):
            for offset, char in enumerate(text):
                buffer.put_char(x + offset, 0, self._style._cell(char))

    def close(self) -> None:
        self._started = False
