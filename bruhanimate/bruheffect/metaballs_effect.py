"""Smooth implicit blobs that merge and separate along independent orbits."""

import numpy as np

from ..bruhutil import Buffer
from ._fields import Field, paint
from ._resize import raster
from .base_effect import BaseEffect
from .settings import MetaballsSettings, validated_settings


class MetaballsEffect(BaseEffect):
    """Moving isosurfaces, corrected for approximately 1:2 terminal cell aspect.

    One update advances the orbital phase. Resize remaps the current orbits,
    retaining their seed and phase without consuming randomness.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: MetaballsSettings | None = None
    ) -> None:
        s = validated_settings(settings, MetaballsSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = MetaballsSettings(**vars(s))
        self._offsets = self.np_rng.uniform(0, np.pi * 2, (s.count, 2))
        self._rates = self.np_rng.uniform(0.6, 1.4, (s.count, 2))
        self._phase = 0.0
        self._paint()

    def _field(self) -> Field:
        h, w = self.buffer.height(), self.buffer.width()
        scale = max(1, min(w, h * 2))
        y, x = np.indices((h, w), dtype=float)
        x, y = (x - (w - 1) / 2) / scale, (y - (h - 1) / 2) * 2 / scale
        field = np.zeros((h, w), dtype=float)
        centers = np.sin(self._offsets + self._phase * self._rates)
        for cx, cy in centers:
            dx = x - cx * w / scale * 0.32
            dy = y - cy * h * 2 / scale * 0.32
            field += (self._settings.radius / 2) ** 2 / (dx * dx + dy * dy + 0.001)
        return field

    def _paint(self) -> None:
        s = self._settings
        field = self._field() / s.threshold
        surface = np.where(field >= 1, 0.25 + 0.75 * (1 - 1 / np.maximum(field, 1)), 0)
        if not s.filled:
            surface = np.where((field >= 0.85) & (field <= 1.25), 0.8, 0)
        paint(
            self.buffer,
            surface,
            (54, 90, 126, 163, 201, 213, 225),
            color=s.color,
            background=self.background,
        )

    def update(self, dt: float) -> None:
        self._phase += self._settings.speed
        self._paint()

    def resize(self, size: tuple[int, int]) -> None:
        self.buffer = raster(self.buffer, size, self.background)
        self._paint()
        super().resize(size)
