"""A damped water surface with reflecting edges and interacting ripples."""

import math

import numpy as np

from ..bruhutil import Buffer
from ._fields import fit, paint
from ._resize import raster
from .base_effect import BaseEffect
from .settings import WaterSettings, validated_settings


class WaterEffect(BaseEffect):
    """Finite-difference waves. Use drop() to inject an impulse at a local cell.

    Updates advance one tick. Draw only copies the current raster. Resize keeps
    both displacement and velocity in the top-left overlap, adding still water.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: WaterSettings | None = None
    ) -> None:
        s = validated_settings(settings, WaterSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = WaterSettings(**vars(s))
        self._height = np.zeros((buffer.height(), buffer.width()), dtype=np.float64)
        self._previous = self._height.copy()

    def drop(self, x: int, y: int, strength: float = 1.0) -> None:
        """Add displacement for the next update; out-of-bounds cells are ignored.

        strength is finite and in [-5, 5]; negative impulses make a depression.
        Coordinates are integer cells in the effect's own viewport.
        """
        if type(x) is not int or type(y) is not int:
            raise TypeError("drop coordinates must be integers")
        if isinstance(strength, bool) or not isinstance(strength, (float, int)):
            raise TypeError("strength must be a number")
        if not math.isfinite(strength) or not -5 <= strength <= 5:
            raise ValueError("strength must be finite and in [-5, 5]")
        if 0 <= y < self._height.shape[0] and 0 <= x < self._height.shape[1]:
            # A smooth disturbance avoids exciting checkerboard grid frequencies.
            top, bottom = max(0, y - 3), min(self.buffer.height(), y + 4)
            left, right = max(0, x - 3), min(self.buffer.width(), x + 4)
            yy, xx = np.mgrid[top:bottom, left:right]
            impulse = strength * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 3)
            self._height[top:bottom, left:right] += impulse
            self._previous[top:bottom, left:right] += impulse

    def update(self, dt: float) -> None:
        s = self._settings
        if self.rng.random() < s.drop_chance:
            self.drop(
                self.rng.randrange(self.buffer.width()),
                self.rng.randrange(self.buffer.height()),
                s.strength,
            )
        padded = np.pad(self._height, 1, mode="edge")
        lap = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            - 4 * self._height
        )
        following = (
            2 * self._height - self._previous + s.wave_speed**2 * lap
        ) * s.damping
        self._previous, self._height = self._height, following
        self._paint()

    def _paint(self) -> None:
        # Removing the mean keeps a uniform water level from lighting the screen.
        field = np.abs(self._height - self._height.mean())
        paint(
            self.buffer,
            np.sqrt(field) * 1.6,
            (17, 24, 31, 39, 45, 159, 231),
            color=self._settings.color,
            background=self.background,
        )

    def resize(self, size: tuple[int, int]) -> None:
        resized = raster(self.buffer, size, self.background)
        self._height, self._previous = (
            fit(self._height, size),
            fit(self._previous, size),
        )
        self.buffer = resized
        self._paint()
        super().resize(size)
