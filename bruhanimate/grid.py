"""Board coordinates, single-cell styling, and clipped grid drawing."""

from __future__ import annotations

import operator
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from .bruhutil.bruhffer import Buffer

_SGR = re.compile(r"\x1b\[[0-9;:]*m")


def _integer(value: int, name: str, minimum: int | None = None) -> int:
    value = operator.index(value)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _shape(rows: Sequence[Sequence[Any]]) -> tuple[int, int]:
    width = len(rows[0]) if len(rows) else 0
    if any(len(row) != width for row in rows):
        raise ValueError("Grid rows must be rectangular")
    return width, len(rows)


def _glyph(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("A grid glyph must be a string or None")
    visible = _SGR.sub("", value)
    if (
        len(visible) != 1
        or unicodedata.category(visible).startswith(("C", "M"))
        or unicodedata.combining(visible)
        or unicodedata.east_asian_width(visible) in ("W", "F")
    ):
        raise ValueError(
            "A grid glyph must contain one single-cell character, optionally SGR styled"
        )
    return value


class GridViewport:
    """Map a rectangular board to a clipped screen region.

    spacing gives columns/rows between glyph anchors. By default a fitting board
    centers inside region=(x, y, width, height), or the whole Buffer. Oversized
    boards anchor at the region's top left. Explicit x/y are screen coordinates.
    camera=(column, row) subtracts a board-space offset from that placement.

    Use single-cell glyphs, optionally wrapped in ANSI SGR color/reset sequences.
    Wide glyphs, combining marks, controls, and raw cursor escapes are rejected.
    Ambiguous-width glyphs (including box drawing) assume a one-cell terminal.
    """

    def __init__(
        self,
        buffer: Buffer,
        columns: int,
        rows: int,
        *,
        x: int | None = None,
        y: int | None = None,
        spacing: tuple[int, int] = (1, 1),
        camera: tuple[int, int] = (0, 0),
        region: tuple[int, int, int, int] | None = None,
    ):
        self.buffer = buffer
        self.columns = _integer(columns, "columns", 0)
        self.rows = _integer(rows, "rows", 0)
        sx, sy = spacing
        self.spacing = (
            _integer(sx, "horizontal spacing", 1),
            _integer(sy, "vertical spacing", 1),
        )
        cx, cy = camera
        self.camera = (_integer(cx, "camera column"), _integer(cy, "camera row"))
        rx, ry, rw, rh = (
            region if region is not None else (0, 0, buffer.width(), buffer.height())
        )
        self.region = (
            _integer(rx, "region x"),
            _integer(ry, "region y"),
            _integer(rw, "region width", 0),
            _integer(rh, "region height", 0),
        )
        rx, ry, rw, rh = self.region
        width = (self.columns - 1) * self.spacing[0] + 1 if self.columns else 0
        height = (self.rows - 1) * self.spacing[1] + 1 if self.rows else 0
        self.x = rx + max(0, (rw - width) // 2) if x is None else _integer(x, "x")
        self.y = ry + max(0, (rh - height) // 2) if y is None else _integer(y, "y")

    @classmethod
    def from_rows(
        cls, buffer: Buffer, rows: Sequence[Sequence[Any]], **layout
    ) -> GridViewport:
        """Infer dimensions, rejecting ragged input. Empty boards are allowed."""
        columns, height = _shape(rows)
        return cls(buffer, columns, height, **layout)

    def to_screen(self, column: int, row: int) -> tuple[int, int]:
        """Transform a board point without clipping it."""
        column, row = operator.index(column), operator.index(row)
        return (
            self.x + (column - self.camera[0]) * self.spacing[0],
            self.y + (row - self.camera[1]) * self.spacing[1],
        )

    def _clip(self) -> tuple[int, int, int, int]:
        x, y, width, height = self.region
        return (
            max(0, x),
            max(0, y),
            min(self.buffer.width(), x + width),
            min(self.buffer.height(), y + height),
        )

    def put(self, column: int, row: int, glyph: str | None) -> bool:
        """Paint a board marker if visible; None is transparent. Return painted."""
        column, row = operator.index(column), operator.index(row)
        if glyph is None:
            return False
        glyph = _glyph(glyph)
        if not (0 <= column < self.columns and 0 <= row < self.rows):
            return False
        x, y = self.to_screen(column, row)
        left, top, right, bottom = self._clip()
        if not (left <= x < right and top <= y < bottom):
            return False
        self.buffer.put_char(x, y, glyph)
        return True

    def draw(
        self,
        rows: Sequence[Sequence[Any]],
        glyph: Mapping[Any, str | None]
        | Callable[[Any, int, int], str | None]
        | None = None,
    ) -> None:
        """Draw visible board cells using a value map or glyph(value, col, row).

        Shape is validated before drawing. Offscreen cells never invoke the glyph
        callback. Without a mapper, None is transparent and other values use str.
        """
        if _shape(rows) != (self.columns, self.rows):
            raise ValueError("Grid shape does not match viewport dimensions")
        left, top, right, bottom = self._clip()
        if right <= left or bottom <= top:
            return
        origin_x, origin_y = self.to_screen(0, 0)
        sx, sy = self.spacing
        first_column = max(0, -((origin_x - left) // sx))
        last_column = min(self.columns, (right - 1 - origin_x) // sx + 1)
        first_row = max(0, -((origin_y - top) // sy))
        last_row = min(self.rows, (bottom - 1 - origin_y) // sy + 1)
        for row in range(first_row, last_row):
            for column in range(first_column, last_column):
                value = rows[row][column]
                if callable(glyph):
                    cell = glyph(value, column, row)
                elif glyph is not None:
                    cell = glyph[value]
                else:
                    cell = None if value is None else str(value)
                self.put(column, row, cell)

    def path(self, points: Iterable[tuple[int, int]], glyph: str = "*") -> None:
        """Paint supplied board points; does not interpolate between vertices."""
        for column, row in points:
            self.put(column, row, glyph)

    def text(self, column: int, row: int, text: str) -> None:
        """Paint consecutive board cells, respecting spacing and clipping."""
        for offset, char in enumerate(text):
            self.put(column + offset, row, char)


def draw_grid(
    buffer: Buffer, rows: Sequence[Sequence[Any]], *, glyph=None, **layout
) -> GridViewport:
    """Draw a rectangular board and return its viewport for paths and markers."""
    viewport = GridViewport.from_rows(buffer, rows, **layout)
    viewport.draw(rows, glyph)
    return viewport
