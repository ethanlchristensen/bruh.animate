"""Rising smoke or sinking ink, advected through an artistic curl field."""

from collections.abc import Iterable

import numpy as np

from ..bruhutil import Buffer
from ._fields import fit, paint, sample
from ._resize import raster
from .base_effect import BaseEffect
from .settings import SmokeSettings, validated_settings


class SmokeEffect(BaseEffect):
    """Density advection with clipped obstacles; not a pressure-solving fluid model.

    Resize retains density and obstacles at the top-left and adds empty cells.
    Each update is one simulation tick; draw never moves or emits density.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: SmokeSettings | None = None
    ) -> None:
        s = validated_settings(settings, SmokeSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = SmokeSettings(**vars(s))
        self._density = np.zeros((buffer.height(), buffer.width()), dtype=np.float64)
        self._obstacles = np.zeros_like(self._density, dtype=bool)
        self._phase = 0.0

    def set_obstacles(self, cells: Iterable[tuple[int, int]]) -> None:
        """Replace solid local (x, y) cells; clip outside cells and clear their ink.

        The iterable is copied immediately. Invalid coordinates leave the old
        mask unchanged. Obstacles prevent density transport through their cells.
        """
        mask = np.zeros_like(self._density, dtype=bool)
        for x, y in cells:
            if type(x) is not int or type(y) is not int:
                raise TypeError("obstacle coordinates must be integers")
            if 0 <= x < self.buffer.width() and 0 <= y < self.buffer.height():
                mask[y, x] = True
        self._obstacles = mask
        self._density[mask] = 0

    def update(self, dt: float) -> None:
        s = self._settings
        self._phase += 0.09
        y, x = np.indices(self._density.shape, dtype=float)
        vx = (
            s.turbulence
            * np.sin(y * 0.32 + self._phase)
            * np.cos(x * 0.15 - self._phase * 0.7)
        )
        vy = s.rise * (1 if s.style == "ink" else -1)
        advected = sample(self._density, x - vx, y - vy)
        advected[self._obstacles] = 0
        padded = np.pad(advected, 1)
        lap = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            - 4 * advected
        )
        self._density = np.maximum(0, (advected + s.diffusion * lap) * s.decay)
        w = self.buffer.width()
        center = w * (0.5 + 0.12 * np.sin(self._phase * 0.3))
        spread = max(0.6, w * s.source_width / 2)
        source = np.exp(-(((np.arange(w) - center) / spread) ** 2)) * s.intensity
        row = 0 if s.style == "ink" else self.buffer.height() - 1
        self._density[row] = np.maximum(
            self._density[row], source * self.rng.uniform(0.85, 1)
        )
        np.clip(self._density, 0, 1, out=self._density)
        self._density[self._obstacles] = 0
        self._paint()

    def _paint(self) -> None:
        palette = (
            (17, 54, 91, 128, 165, 207, 225)
            if self._settings.style == "ink"
            else (236, 240, 244, 248, 252, 255)
        )
        paint(
            self.buffer,
            np.sqrt(self._density),
            palette,
            color=self._settings.color,
            background=self.background,
        )

    def resize(self, size: tuple[int, int]) -> None:
        resized = raster(self.buffer, size, self.background)
        self._density = fit(self._density, size)
        self._obstacles = fit(self._obstacles.astype(float), size).astype(bool)
        self.buffer = resized
        self._paint()
        super().resize(size)
