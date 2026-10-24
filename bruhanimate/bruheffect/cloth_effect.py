"""A pinned, waving flag that can carry text or custom ASCII art."""

import math
from collections.abc import Sequence

from ..bruhutil import Buffer
from ._resize import raster
from .base_effect import BaseEffect
from .settings import ClothSettings, _glyph, validated_settings


class ClothEffect(BaseEffect):
    """Kinematic cloth with an anchored left edge and shaded traveling folds.

    image accepts text or rows of printable single-cell glyphs, copied on input.
    Custom art is centered on the cloth at its original size and clipped to fit.
    Resize preserves art and wave phase. No physical spring solver is involved.
    """

    def __init__(
        self,
        buffer: Buffer,
        background: str,
        settings: ClothSettings | None = None,
        *,
        image: str | Sequence[str] | None = None,
    ) -> None:
        s = validated_settings(settings, ClothSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = ClothSettings(**vars(s))
        self._phase = 0.0
        self._image: tuple[str, ...] | None = None
        if image is not None:
            self.set_image(image)
        self._paint()

    def set_image(self, image: str | Sequence[str] | None) -> None:
        """Copy ASCII rows, or use None to restore the configured pattern.

        Ragged rows are space-padded. Empty art, ANSI escapes and wide/combining
        glyphs are rejected. A change appears on the next update or resize.
        """
        if image is None:
            self._image = None
            return
        if not isinstance(image, (str, Sequence)):
            raise TypeError("image must be text or a sequence of rows")
        rows = tuple(image.splitlines()) if isinstance(image, str) else tuple(image)
        if any(not isinstance(row, str) for row in rows):
            raise TypeError("image rows must be strings")
        if not rows or not max(map(len, rows)):
            raise ValueError("image must contain at least one cell")
        for row in rows:
            for glyph in row:
                _glyph(glyph, "image")
        width = max(map(len, rows))
        self._image = tuple(row.ljust(width) for row in rows)

    def _paint(self) -> None:
        s = self._settings
        self.buffer.clear_buffer(val=self.background)
        h, w = self.buffer.height(), self.buffer.width()
        left, top = w // 12, h // 4
        width, height = max(1, w * 5 // 6), max(1, h // 2)
        art = self._image or ((s.text,) if s.pattern == "text" else None)
        for col in range(width):
            u = col / max(1, width - 1)
            angle = u * s.wavelength * math.tau - self._phase
            offset = round(math.sin(angle) * u * s.amplitude * h)
            shade = int((math.cos(angle) + 1) * 2)
            for row in range(height):
                stripe = min(2, row * 3 // height)
                glyph = "#"
                bg = (
                    (24, 31, 38, 45, 51),
                    (160, 196, 202, 208, 214),
                    (22, 28, 34, 40, 46),
                )[stripe][shade]
                if s.pattern == "checker":
                    dark = (col // 4 + row // 2) % 2 == 0
                    bg = (235 if dark else 247) + shade
                    glyph = "." if dark else "#"
                if art:
                    ax, ay = (
                        col - (width - len(art[0])) // 2,
                        row - (height - len(art)) // 2,
                    )
                    glyph = (
                        art[ay][ax]
                        if 0 <= ay < len(art) and 0 <= ax < len(art[0])
                        else " "
                    )
                    bg = 17 + shade * 6
                cell = (
                    f"\x1b[38;5;231;48;5;{bg}m{glyph if art else ' '}\x1b[0m"
                    if s.color
                    else glyph
                )
                self.buffer.put_char(left + col, top + row + offset, cell)
        if left > 0:
            for row in range(top, min(h, top + height + h // 4)):
                self.buffer.put_char(left - 1, row, "|")

    def update(self, dt: float) -> None:
        self._phase += self._settings.speed
        self._paint()

    def resize(self, size: tuple[int, int]) -> None:
        self.buffer = raster(self.buffer, size, self.background)
        self._paint()
        super().resize(size)
