"""State-preserving raster allocation shared by explicit built-in adapters."""

from ..bruhutil import Buffer
from ..resize import _size


def raster(
    buffer: Buffer, size: tuple[int, int], background: str, *, bottom: bool = False
) -> Buffer:
    """Copy the retained overlap; new cells paint the background pattern."""
    _size(size)
    width, height = size
    result = Buffer(height, width)
    pattern = background or " "
    for y in range(height):
        result.put_at(0, y, (pattern * (width // len(pattern) + 1))[:width])
    rows, columns = min(height, buffer.height()), min(width, buffer.width())
    source_y = buffer.height() - rows if bottom else 0
    target_y = height - rows if bottom else 0
    for y in range(rows):
        result.buffer[target_y + y][:columns] = buffer.buffer[source_y + y][:columns]
    return result
