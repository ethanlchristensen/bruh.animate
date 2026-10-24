"""Small array/raster helpers shared by the field simulations."""

import numpy as np
from numpy.typing import NDArray

from ..bruhutil import Buffer

Field = NDArray[np.float64]


def fit(field: Field, size: tuple[int, int]) -> Field:
    """Copy the top-left overlap into an otherwise empty field."""
    width, height = size
    result = np.zeros((height, width), dtype=np.float64)
    rows, cols = min(height, field.shape[0]), min(width, field.shape[1])
    result[:rows, :cols] = field[:rows, :cols]
    return result


def sample(field: Field, x: Field, y: Field, *, wrap: bool = False) -> Field:
    """Bilinear samples, with periodic or zero-valued exterior boundaries."""
    h, w = field.shape
    if wrap:
        x, y = x % w, y % h
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    result = np.zeros_like(x, dtype=np.float64)
    for dx, dy, weight in (
        (0, 0, (1 - fx) * (1 - fy)),
        (1, 0, fx * (1 - fy)),
        (0, 1, (1 - fx) * fy),
        (1, 1, fx * fy),
    ):
        xx, yy = x0 + dx, y0 + dy
        valid = True if wrap else ((xx >= 0) & (xx < w) & (yy >= 0) & (yy < h))
        result += field[yy % h, xx % w] * weight * valid
    return result


def paint(
    buffer: Buffer,
    field: Field,
    palette: tuple[int, ...],
    *,
    color: bool,
    background: str,
) -> None:
    """Quantize a normalized field into cached, single-cell styled glyphs."""
    glyphs = " .:-=+*#%@"
    levels = (np.clip(field, 0, 1) * (len(glyphs) - 1)).astype(int)
    cells = [background]
    for index, glyph in enumerate(glyphs[1:], 1):
        shade = palette[(index - 1) * (len(palette) - 1) // (len(glyphs) - 2)]
        cells.append(f"\x1b[38;5;{shade}m{glyph}\x1b[0m" if color else glyph)
    for y, row in enumerate(levels):
        buffer.buffer[y][:] = [cells[int(level)] for level in row]
