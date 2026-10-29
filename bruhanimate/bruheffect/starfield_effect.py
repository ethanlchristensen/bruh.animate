"""Perspective star flight through a bounded cloud of 3D points."""

import numpy as np

from ..bruhutil import Buffer
from ._fields import paint
from ._resize import raster
from .base_effect import BaseEffect
from .settings import StarfieldSettings, validated_settings


class StarfieldEffect(BaseEffect):
    """Endless perspective flight with optional rotation and fading streaks.

    Depth runs from 1 (far) to 0.08 (near); each tick subtracts speed. Departing
    stars recycle at the far plane without connecting a streak to their old
    position. Brightness reflects depth, with nearer stars winning overlaps.
    speed=0 freezes all state. Resize retains 3D positions, clears screen-space
    trails and reprojects without advancing time or consuming randomness.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: StarfieldSettings | None = None
    ):
        s = validated_settings(settings, StarfieldSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = StarfieldSettings(**vars(s))
        self._stars = self.np_rng.uniform(-1, 1, (s.count, 3))
        self._stars[:, 2] = self.np_rng.uniform(0.08, 1, s.count)
        self._trail = np.zeros((buffer.height(), buffer.width()))
        self._deposit(self._project(), 0.25 + 0.75 * (1 - self._stars[:, 2]))
        self._paint()

    def _project(self) -> np.ndarray:
        size = np.array([self.buffer.width(), self.buffer.height()])
        return size / 2 + self._stars[:, :2] / self._stars[:, 2, None] * size * (
            self._settings.zoom / 2
        )

    def _deposit(self, points: np.ndarray, brightness: np.ndarray) -> None:
        valid = (
            (points >= 0) & (points < [self.buffer.width(), self.buffer.height()])
        ).all(axis=1)
        cells = points[valid].astype(np.intp)
        np.maximum.at(self._trail, (cells[:, 1], cells[:, 0]), brightness[valid])

    def update(self, dt: float) -> None:
        s = self._settings
        if s.speed == 0:
            return
        old = self._project()
        self._trail *= s.trails
        self._stars[:, 2] -= s.speed
        # Recycle before projection; no zero/negative depth reaches division.
        recycled = self._stars[:, 2] < 0.08
        self._stars[recycled, 2] = 1.0
        c, sn = np.cos(s.twist), np.sin(s.twist)
        self._stars[:, :2] = self._stars[:, :2] @ np.array([[c, sn], [-sn, c]])
        projected = self._project()
        recycled |= (
            (projected < 0) | (projected >= [self.buffer.width(), self.buffer.height()])
        ).any(axis=1)
        self._stars[recycled, :2] = self.np_rng.uniform(-1, 1, (int(recycled.sum()), 2))
        self._stars[recycled, 2] = 1.0
        projected = self._project()
        old[recycled] = projected[recycled]
        brightness = 0.25 + 0.75 * (1 - self._stars[:, 2])
        # Bounded streak sampling; trails=0 renders only current points.
        samples = 12 if s.trails > 0 else 1
        for fraction in np.linspace(1 / samples, 1, samples):
            self._deposit(old + (projected - old) * fraction, brightness)
        self._paint()

    def _paint(self) -> None:
        paint(
            self.buffer,
            self._trail,
            (17, 18, 24, 31, 38, 45, 81, 117, 159, 231),
            color=self._settings.color,
            background=self.background,
        )

    def resize(self, size: tuple[int, int]) -> None:
        self.buffer = raster(self.buffer, size, self.background)
        self._trail = np.zeros((size[1], size[0]))
        self._deposit(self._project(), 0.25 + 0.75 * (1 - self._stars[:, 2]))
        self._paint()
        super().resize(size)
