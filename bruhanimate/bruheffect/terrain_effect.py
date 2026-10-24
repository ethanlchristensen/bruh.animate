"""Perspective voxel-space flyover of a seeded, periodic height field."""

import numpy as np

from ..bruhutil import Buffer
from ._fields import Field, paint, sample
from ._resize import raster
from .base_effect import BaseEffect
from .settings import TerrainSettings, validated_settings


class TerrainEffect(BaseEffect):
    """Coherent hills projected into a moving perspective view.

    A bounded seeded noise tile supplies four octaves. Travel wraps through that
    tile; resize preserves the tile and camera position and repaints at once.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: TerrainSettings | None = None
    ) -> None:
        s = validated_settings(settings, TerrainSettings)
        super().__init__(buffer, background, seed=s.seed)
        self._settings = TerrainSettings(**vars(s))
        self._noise = self.np_rng.random((128, 128))
        self._travel = 0.0
        self._paint()

    def _height(self, x: Field, z: Field) -> Field:
        result = np.zeros_like(x)
        for octave in range(4):
            frequency = self._settings.scale * 2**octave
            # Smoothstep interpolation removes angular ridges between grid cells.
            xx, zz = x * frequency, z * frequency
            ix, iz = np.floor(xx), np.floor(zz)
            fx, fz = xx - ix, zz - iz
            result += (
                sample(
                    self._noise,
                    ix + fx * fx * (3 - 2 * fx),
                    iz + fz * fz * (3 - 2 * fz),
                    wrap=True,
                )
                / 2**octave
            )
        return np.clip((result / 1.875 - 0.5) * 2.2 + 0.5, 0, 1)

    def _paint(self) -> None:
        s = self._settings
        h, w = self.buffer.height(), self.buffer.width()
        surface = np.zeros((h, w), dtype=float)
        occlusion = np.full(w, h, dtype=int)
        rays = np.linspace(-1, 1, w) * max(0.5, w / max(1, h * 2))
        depths = np.geomspace(2, 45, 72)
        world_x = rays[None, :] * depths[:, None]
        world_z = np.broadcast_to(self._travel + depths[:, None], (len(depths), w))
        samples = self._height(world_x, world_z)
        # Directional light reveals slopes instead of drawing flat elevation bands.
        slope = self._height(world_x + 0.3, world_z + 0.3) - samples
        lighting = np.clip(0.65 - slope * 5, 0.2, 1)
        for depth, elevations, light in zip(depths, samples, lighting):
            projected = np.clip(
                (
                    h * s.horizon
                    + (1.1 - elevations * s.roughness * 1.5) * h * 4 / depth
                ).astype(int),
                0,
                h,
            )
            shades = 0.15 + light * 0.7
            if s.style == "contours":
                shades = np.where(
                    (elevations * 30) % 1 < 0.25, 0.95, 0.25 + elevations * 0.35
                )
            shades *= 1 - depth / 100
            for x in np.flatnonzero(projected < occlusion):
                surface[projected[x] : occlusion[x], x] = shades[x]
            occlusion = np.minimum(projected, occlusion)
        paint(
            self.buffer,
            surface,
            (22, 28, 64, 100, 136, 180, 230, 255),
            color=s.color,
            background=self.background,
        )

    def update(self, dt: float) -> None:
        self._travel = (self._travel + self._settings.speed) % (
            128 / self._settings.scale
        )
        self._paint()

    def resize(self, size: tuple[int, int]) -> None:
        self.buffer = raster(self.buffer, size, self.background)
        self._paint()
        super().resize(size)
