"""
Copyright 2023 Ethan Christensen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import math

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil import Buffer
from ._resize import raster
from .base_effect import BaseEffect
from .settings import PerlinSettings, validated_settings


def _heat(r: float) -> int:
    r = max(0.0, min(1.0, r))
    if r < 0.25:
        return 17 + int(r * 4 * 18)
    elif r < 0.5:
        return 51 + int((r - 0.25) * 4 * 12)
    elif r < 0.75:
        return 82 + int((r - 0.5) * 4 * 12)
    else:
        return 220 + int((r - 0.75) * 4 * 3)


class PerlinEffect(BaseEffect):
    """
    Smooth animated noise field.

    Multiple octaves of sine-wave interference are combined to produce
    fractal-like smooth noise that scrolls and pulses over time. A
    configurable threshold gates which parts of the field are drawn,
    controlling density. Color maps noise intensity through a heat
    palette when enabled.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: PerlinSettings | None = None
    ):
        s = validated_settings(settings, PerlinSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.color = s.color
        self.char = s.char
        self.octaves = s.octaves
        self.speed = s.speed
        self.threshold = s.threshold
        self._w = buffer.width()
        self._h = buffer.height()
        self._t = 0.0

        rng = self.np_rng
        self._offsets = rng.uniform(0, 2 * math.pi, max(8, self.octaves)).astype(
            np.float32
        )

        cols = np.arange(self._w)
        rows = np.arange(self._h)
        X, Y = np.meshgrid(cols, rows)
        self._xs = (X / self._w * 4 * math.pi).astype(np.float32)
        self._ys = (Y / self._h * 4 * math.pi).astype(np.float32)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self._t += self.speed

        self._paint()

    def _paint(self) -> None:
        self.buffer.clear_buffer(val=self.background)
        noise = np.zeros((self._h, self._w), dtype=np.float32)
        amp, total = 1.0, 0.0
        for i in range(self.octaves):
            freq = float(2**i)
            phase = float(self._offsets[i]) + self._t * (0.4 + i * 0.25)
            noise += amp * (
                np.sin(self._xs * freq + phase)
                * np.cos(self._ys * freq * 0.7 + phase * 1.3)
                * 0.5
                + np.sin(self._xs * freq * 1.5 + phase * 0.8)
                * np.sin(self._ys * freq * 1.2 + phase * 0.6)
                * 0.5
            )
            total += amp
            amp *= 0.5
        noise = (noise / total + 1.0) / 2.0

        lit_r, lit_c = np.where(noise > self.threshold)
        mags = noise[lit_r, lit_c]
        for i in range(len(lit_r)):
            color = _heat(float(mags[i])) if self.color else None
            ch = bc(self.char, color=color) if color is not None else self.char
            self.buffer.put_char(int(lit_c[i]), int(lit_r[i]), ch)

    def resize(self, size: tuple[int, int]) -> None:
        """Rebuild sampling coordinates, retaining phase and seeded offsets."""
        self.buffer = raster(self.buffer, size, self.background)
        self._w, self._h = size
        x, y = np.meshgrid(np.arange(self._w), np.arange(self._h))
        self._xs = (x / self._w * 4 * math.pi).astype(np.float32)
        self._ys = (y / self._h * 4 * math.pi).astype(np.float32)
        self._paint()
        super().resize(size)
