"""Pure, viewport-aware masks usable with any animation Layer."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .grid import _glyph

CellMask = Callable[[int, int, tuple[int, int]], bool]
"""Predicate (x, y, (width, height)) in destination cells; True allows paint.

Called during draw. It must be pure and must not advance animation or consume
input/randomness. Region clipping and transparency still apply independently.
"""


@dataclass(frozen=True, init=False)
class ImageMask:
    """Immutable mask from plain ASCII rows: non-space cells allow painting.

    x/y locate the mask in destination coordinates; None centers that axis on
    every draw, including after resize. Ragged/empty rows are allowed. invert
    selects the complement, including cells outside the image. The mask owns
    no animation or resources and works with any Layer child, not just images.
    """

    rows: tuple[str, ...]
    x: int | None
    y: int | None
    invert: bool
    width: int

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: int | None = None,
        y: int | None = None,
        invert: bool = False,
    ) -> None:
        for name, value in (("x", x), ("y", y)):
            if value is not None and type(value) is not int:
                raise TypeError(f"{name} must be an integer or None")
        if type(invert) is not bool:
            raise TypeError("invert must be a bool")
        rows = tuple(image.splitlines() if isinstance(image, str) else image)
        for row in rows:
            if not isinstance(row, str):
                raise TypeError("image rows must be strings")
            for char in row:
                _glyph(char)
        for name, attribute in (
            ("rows", rows),
            ("x", x),
            ("y", y),
            ("invert", invert),
            ("width", max(map(len, rows), default=0)),
        ):
            object.__setattr__(self, name, attribute)

    def __call__(self, x: int, y: int, size: tuple[int, int]) -> bool:
        left = (size[0] - self.width) // 2 if self.x is None else self.x
        top = (size[1] - len(self.rows)) // 2 if self.y is None else self.y
        column, row = x - left, y - top
        inside = (
            0 <= row < len(self.rows)
            and 0 <= column < len(self.rows[row])
            and self.rows[row][column] != " "
        )
        return not inside if self.invert else inside
