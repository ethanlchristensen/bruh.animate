"""Procedural branching growth with bounded live tips and fading old branches."""

import math

import numpy as np

from ..bruhutil import Buffer
from ._fields import fit, paint
from ._resize import raster
from .base_effect import BaseEffect
from .settings import GrowthSettings, validated_settings


class GrowthEffect(BaseEffect):
    """Endless coral, forest or electric shoots grown from the bottom edge.

    Updates are simulation ticks; speed=0 freezes all state. At most max_tips
    grow at once. A fresh generation starts after cycle_ticks or when all tips
    leave the viewport. Old branches fade in a fixed-size raster, not a history.
    Resize retains top-left trails and in-bounds tips without reseeding; if none
    remain, the next update plants roots. Draw never grows branches.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: GrowthSettings | None = None
    ):
        s = validated_settings(settings, GrowthSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = GrowthSettings(**vars(s))
        self._trail = np.zeros((buffer.height(), buffer.width()))
        self._tips: list[tuple[float, float, float]] = []
        self._age = 0
        self._plant()
        self._paint()

    def _plant(self) -> None:
        s = self._settings
        self._tips = [
            (
                self.rng.uniform(0, self.buffer.width() - 1),
                float(self.buffer.height() - 1),
                -math.pi / 2 + self.rng.uniform(-0.3, 0.3),
            )
            for _ in range(s.roots)
        ]
        self._age = 0

    def update(self, dt: float) -> None:
        s = self._settings
        if s.speed == 0:
            return
        if not self._tips or self._age >= s.cycle_ticks:
            self._plant()
        self._age += 1
        self._trail *= s.decay
        survivors: list[tuple[float, float, float]] = []
        branches: list[tuple[float, float, float]] = []
        width, height = self.buffer.width(), self.buffer.height()
        for x, y, angle in self._tips:
            angle = min(
                -0.18, max(-math.pi + 0.18, angle + self.rng.uniform(-0.12, 0.12))
            )
            dx, dy = math.cos(angle) * s.speed * 2, math.sin(angle) * s.speed
            for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
                px, py = x + dx * fraction, y + dy * fraction
                if 0 <= px < width and 0 <= py < height:
                    self._trail[int(py), int(px)] = 1.0
            x, y = x + dx, y + dy
            if 0 <= x < width and 0 <= y < height:
                survivors.append((x, y, angle))
                if self.rng.random() < s.branch_chance:
                    direction = self.rng.choice((-1, 1))
                    branches.append((x, y, angle + direction * s.spread))
        # Existing shoots take priority; no persistent branch/segment list grows.
        self._tips = (survivors + branches)[: s.max_tips]
        self._paint()

    def _paint(self) -> None:
        palettes = {
            "coral": (52, 88, 125, 161, 168, 175, 182, 210, 217, 224),
            "forest": (22, 28, 34, 40, 70, 76, 112, 148, 190, 229),
            "electric": (17, 18, 19, 27, 33, 39, 81, 117, 159, 231),
        }
        paint(
            self.buffer,
            self._trail,
            palettes[self._settings.palette],
            color=self._settings.color,
            background=self.background,
        )

    def resize(self, size: tuple[int, int]) -> None:
        resized = raster(self.buffer, size, self.background)
        self._trail = fit(self._trail, size)
        self._tips = [
            (x, y, angle)
            for x, y, angle in self._tips
            if 0 <= x < size[0] and 0 <= y < size[1]
        ]
        self.buffer = resized
        self._paint()
        super().resize(size)
