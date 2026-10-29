"""Particles tracing a smooth, slowly evolving vector field."""

import numpy as np

from ..bruhutil import Buffer
from ._fields import fit, paint
from ._resize import raster
from .base_effect import BaseEffect
from .settings import FlowSettings, validated_settings


class FlowEffect(BaseEffect):
    """Endless curling trails with a fixed particle budget and toroidal wrapping.

    Each update advances one tick, independently of dt; speed=0 freezes all state.
    Resize retains top-left trails and wraps particles into the new viewport,
    without consuming randomness. Draw only copies the latest raster.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: FlowSettings | None = None
    ):
        s = validated_settings(settings, FlowSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = FlowSettings(**vars(s))
        self._points = self.np_rng.random((s.count, 2)) * [
            buffer.width(),
            buffer.height(),
        ]
        self._trail = np.zeros((buffer.height(), buffer.width()))
        self._phase = 0.0
        self._paint()

    def update(self, dt: float) -> None:
        s = self._settings
        if s.speed == 0:
            return
        self._trail *= s.decay
        self._phase = (self._phase + 0.012 * s.speed) % (2 * np.pi)
        x, y = self._points.T
        # Account for terminal cells being roughly twice as tall as wide.
        x, y = x * s.scale, y * s.scale * 2
        # The perpendicular gradient of a smooth potential forms circulating
        # paths instead of concentrating every particle at an attracting point.
        x, y = x + self._phase, y - self._phase
        diagonal = 0.6 * np.cos((x + y) * 0.6 + self._phase)
        vx = np.sin(x) * np.cos(y) + diagonal
        vy = -np.cos(x) * np.sin(y) - diagonal
        delta = np.column_stack((vx, vy * 0.5)) * (s.speed / 1.6)
        size = np.array([self.buffer.width(), self.buffer.height()])
        # Sample before wrapping, so boundary crossings never draw a screen-wide line.
        for fraction in (0.25, 0.5, 0.75, 1.0):
            cells = ((self._points + delta * fraction) % size).astype(np.intp)
            self._trail[cells[:, 1], cells[:, 0]] = 1.0
        self._points = (self._points + delta) % size
        self._paint()

    def _paint(self) -> None:
        palettes = {
            "neon": (17, 54, 91, 128, 165, 201, 207, 213, 225, 231),
            "ocean": (17, 18, 19, 25, 31, 37, 43, 50, 87, 159),
            "ember": (52, 88, 124, 160, 196, 202, 208, 214, 220, 229),
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
        self._points %= np.array(size)
        self.buffer = resized
        self._paint()
        super().resize(size)
