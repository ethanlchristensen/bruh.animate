"""Shared computer artwork and demo-only screen geometry; no device access."""

from typing import Literal

from bruhanimate import Buffer, get_image
from bruhanimate.resize import _size

ComputerStyle = Literal["classic", "expanded", "box"]

# Snapshot the bundled art; never mutate the image catalog's shared rows.
COMPUTER = tuple(row.rstrip() for row in get_image("computer"))
COMPUTER_WIDTH = max(map(len, COMPUTER))
# Half-open column spans of the angled monitor opening, in artwork coordinates.
# The comma on row 11 is part of the original bezel and remains visible.
SCREEN_SPANS = (
    (3, 41, 45),
    (4, 32, 45),
    (5, 22, 45),
    (6, 22, 45),
    (7, 22, 45),
    (8, 22, 45),
    (9, 22, 45),
    (10, 22, 45),
    (11, 22, 43),
    (11, 44, 45),
    (12, 22, 39),
    (13, 22, 30),
)


def _expand_computer(
    extra_width: int,
    extra_height: int,
) -> tuple[tuple[str, ...], tuple[tuple[int, int, int], ...]]:
    """Insert center columns and straight monitor rows, preserving the corners.

    The vertical seam crosses the screen/keyboard at column 33. Row 7 provides
    the horizontal seam's straight side walls. Apply the same expansion to the
    opening mask, keeping the original comma and all bezel glyphs intact.
    """
    source_rows = [*range(8), *([7] * extra_height), *range(8, len(COMPUTER))]
    rows = []
    spans = []
    for y, source_y in enumerate(source_rows):
        row = COMPUTER[source_y].ljust(COMPUTER_WIDTH)
        # At shading transitions, continue the adjacent face rather than
        # stretching a decorative letter/question mark across the whole seam.
        fill = {0: "8", 2: "|", 15: "8", 17: ":", 21: "8", 27: "8"}.get(
            source_y, row[32]
        )
        rows.append((row[:33] + fill * extra_width + row[33:]).rstrip())
        for old_y, start, stop in SCREEN_SPANS:
            if old_y == source_y:
                spans.append(
                    (
                        y,
                        start + (extra_width if start >= 33 else 0),
                        stop + (extra_width if stop >= 33 else 0),
                    )
                )
    return tuple(rows), tuple(spans)


def _origin(buffer: Buffer) -> tuple[int, int]:
    """Center horizontally; keep the monitor visible when height is limited."""
    return (
        (buffer.width() - COMPUTER_WIDTH) // 2,
        max(1, (buffer.height() - len(COMPUTER)) // 2),
    )


def _paint(buffer: Buffer, x: int, y: int, text: str, style: str) -> None:
    """Keep captions separate and clip styled glyphs as individual cells."""
    if not 1 <= y < buffer.height() - 1:
        return
    for offset, char in enumerate(text):
        buffer.put_char(x + offset, y, f"\x1b[{style}m{char}\x1b[0m")


def _monitor_mask(x: int, y: int, size: tuple[int, int]) -> bool:
    left = (size[0] - COMPUTER_WIDTH) // 2
    top = max(1, (size[1] - len(COMPUTER)) // 2)
    return 1 <= y < size[1] - 1 and any(
        row == y - top and start <= x - left < stop for row, start, stop in SCREEN_SPANS
    )


class ComputerFrame:
    """Fit local audio into classic/expanded artwork or a responsive box monitor.

    Classic requires the complete 67x30 artwork plus two caption rows. Smaller
    viewports use box geometry without changing the preferred style. Projection
    is prepared on resize, never during simulation or painting. Expanded inserts
    center columns and monitor rows to fit the viewport with a small margin.
    """

    def __init__(self, size: tuple[int, int], style: ComputerStyle) -> None:
        _size(size)
        if style not in ("classic", "expanded", "box"):
            raise ValueError("computer must be 'classic', 'expanded', or 'box'")
        self.size = size
        width, height = size
        self.active_style: ComputerStyle = (
            style
            if style != "box"
            and width >= COMPUTER_WIDTH
            and height >= len(COMPUTER) + 2
            else "box"
        )
        self.body: list[tuple[int, int, str]] = []
        self.cells: list[tuple[int, int, int, int]] = []
        if self.active_style != "box":
            extra_w = max(0, width - COMPUTER_WIDTH - 4) if style == "expanded" else 0
            extra_h = max(0, height - len(COMPUTER) - 4) if style == "expanded" else 0
            art, spans = _expand_computer(extra_w, extra_h)
            left = (width - COMPUTER_WIDTH - extra_w) // 2
            top = max(1, (height - len(art)) // 2)
            self.body = [(left, top + row, text) for row, text in enumerate(art)]
            columns = [
                [row for row, start, stop in spans if start <= x < stop]
                for x in range(22, 45 + extra_w)
            ]
            self.screen_size = (len(columns), max(map(len, columns)))
            for x, rows in enumerate(columns):
                for index, y in enumerate(rows):
                    # Follow each column's sloped top/bottom so every bar has a
                    # visible base, instead of clipping a rectangular raster.
                    source_y = round(
                        index * (self.screen_size[1] - 1) / (len(rows) - 1)
                    )
                    self.cells.append((left + 22 + x, top + y, x, source_y))
        else:
            self._box(width, height)

    def _box(self, width: int, height: int) -> None:
        if width < 3 or height < 5:
            x, y, inner_w, inner_h = 0, 1, width, max(1, height - 2)
        else:
            roomy = width >= 12 and height >= 10
            left, right = (1, width - 2) if roomy else (0, width - 1)
            bottom = height - 6 if roomy else height - 2
            inner_w, inner_h = right - left - 1, bottom - 2
            x, y = left + 1, 2
            self.body.append((left, 1, "." + "-" * inner_w + "."))
            for row in range(2, bottom):
                self.body.extend(((left, row, "|"), (right, row, "|")))
            self.body.append((left, bottom, "'" + "-" * inner_w + "'"))
            if roomy:
                center = width // 2
                self.body.extend(
                    (
                        (center - 2, bottom + 1, "|___|"),
                        (left, bottom + 2, "/" + "-" * inner_w + "\\"),
                        (left, bottom + 3, "|" + ("[] " * width)[:inner_w] + "|"),
                        (left, bottom + 4, "'" + "-" * inner_w + "'"),
                    )
                )
        self.screen_size = (inner_w, inner_h)
        self.cells = [
            (x + sx, y + sy, sx, sy)
            for sy in range(inner_h)
            for sx in range(inner_w)
            if 1 <= y + sy < height - 1
        ]

    def draw(self, target: Buffer, screen: Buffer) -> None:
        """Paint opaque body/screen cells, leaving the background outside intact."""
        for x, y, text in self.body:
            start = len(text) - len(text.lstrip())
            _paint(target, x + start, y, text[start:], "38;5;250;49")
        for x, y, sx, sy in self.cells:
            target.put_char(x, y, screen.get_char(sx, sy))
