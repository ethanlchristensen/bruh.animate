"""Viewport-bounded drawing in integer terminal-cell coordinates."""

from .bruhutil.bruhffer import Buffer
from .grid import _glyph

type Point = tuple[int, int]
type Rect = tuple[int, int, int, int]


def _integers(value: tuple[int, ...], count: int, name: str) -> None:
    if not isinstance(value, tuple) or len(value) != count:
        raise TypeError(f"{name} must be a tuple of {count} integers")
    if any(type(item) is not int for item in value):
        raise TypeError(f"{name} must contain integers")


def _rect(value: Rect, name: str) -> None:
    _integers(value, 4, name)
    if value[2] < 0 or value[3] < 0:
        raise ValueError(f"{name} dimensions must be non-negative")


def _clip(buffer: Buffer, clip: Rect | None) -> Rect:
    if clip is None:
        return 0, 0, buffer.width(), buffer.height()
    _rect(clip, "clip")
    x, y, width, height = clip
    return (
        max(0, x),
        max(0, y),
        min(buffer.width(), x + width),
        min(buffer.height(), y + height),
    )


def draw_line(
    buffer: Buffer,
    start: Point,
    end: Point,
    glyph: str = "#",
    *,
    clip: Rect | None = None,
) -> None:
    """Paint an inclusive, one-cell line, clipped without walking offscreen cells.

    Coordinates are integer (column, row) pairs. ``clip`` is an optional
    (x, y, width, height) destination rectangle. Ties round toward the end of
    the minor axis after ordering along the major axis; reversing endpoints
    paints exactly the same cells. Work is bounded by the viewport dimensions,
    even for enormous offscreen coordinates. Glyphs may contain ANSI SGR styling.
    """
    _integers(start, 2, "start")
    _integers(end, 2, "end")
    glyph = _glyph(glyph)
    left, top, right, bottom = _clip(buffer, clip)
    x0, y0 = start
    x1, y1 = end
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx >= dy:
        if x0 > x1:
            x0, y0, x1, y1 = x1, y1, x0, y0
        sign = 1 if y1 >= y0 else -1
        for x in range(max(left, x0), min(right, x1 + 1)):
            y = y0 if dx == 0 else y0 + sign * ((2 * dy * (x - x0) + dx) // (2 * dx))
            if top <= y < bottom:
                buffer.put_char(x, y, glyph)
    else:
        if y0 > y1:
            x0, y0, x1, y1 = x1, y1, x0, y0
        sign = 1 if x1 >= x0 else -1
        for y in range(max(top, y0), min(bottom, y1 + 1)):
            x = x0 + sign * ((2 * dx * (y - y0) + dy) // (2 * dy))
            if left <= x < right:
                buffer.put_char(x, y, glyph)


def draw_rect(
    buffer: Buffer,
    bounds: Rect,
    glyph: str = "#",
    *,
    filled: bool = False,
    clip: Rect | None = None,
) -> None:
    """Paint a rectangle in cells, optionally filled; zero dimensions paint nothing.

    Bounds and clip are (x, y, width, height). Clipping never creates new outline
    edges. No aspect correction is applied: terminal cells are usually taller
    than they are wide. Work is bounded by the visible intersection.
    """
    _rect(bounds, "bounds")
    if not isinstance(filled, bool):
        raise TypeError("filled must be a bool")
    glyph = _glyph(glyph)
    left, top, right, bottom = _clip(buffer, clip)
    x, y, width, height = bounds
    for row in range(max(top, y), min(bottom, y + height)):
        for column in range(max(left, x), min(right, x + width)):
            if filled or column in (x, x + width - 1) or row in (y, y + height - 1):
                buffer.put_char(column, row, glyph)


def draw_ellipse(
    buffer: Buffer,
    bounds: Rect,
    glyph: str = "#",
    *,
    filled: bool = False,
    clip: Rect | None = None,
) -> None:
    """Paint a cell-center ellipse in (x, y, width, height) bounds.

    An outline consists of included cells with at least one of their four
    neighbors outside the ellipse. Clipping preserves that original outline.
    Empty dimensions paint nothing. Computation uses integer arithmetic and
    visits only visible cells. Dimensions are cells, with no aspect correction.
    """
    _rect(bounds, "bounds")
    if not isinstance(filled, bool):
        raise TypeError("filled must be a bool")
    glyph = _glyph(glyph)
    left, top, right, bottom = _clip(buffer, clip)
    x, y, width, height = bounds
    if width == 0 or height == 0:
        return
    w2, h2 = width * width, height * height

    def inside(column: int, row: int) -> bool:
        return (2 * (column - x) + 1 - width) ** 2 * h2 + (
            2 * (row - y) + 1 - height
        ) ** 2 * w2 <= w2 * h2

    for row in range(max(top, y), min(bottom, y + height)):
        for column in range(max(left, x), min(right, x + width)):
            if inside(column, row) and (
                filled
                or not all(
                    inside(column + dx, row + dy)
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                )
            ):
                buffer.put_char(column, row, glyph)
