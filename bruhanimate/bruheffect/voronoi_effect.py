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

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil import Buffer
from .base_effect import BaseEffect
from .settings import VoronoiSettings, validated_settings


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


class VoronoiEffect(BaseEffect):
    """
    Animated Voronoi diagram.

    A set of seed points drift around the screen, bouncing off the edges.
    Every pixel is colored by its nearest seed, producing a continuously
    shifting stained-glass pattern. Seed positions are highlighted with a
    bright marker.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: VoronoiSettings | None = None
    ):
        s = validated_settings(settings, VoronoiSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.color = s.color
        self.char = s.char
        self.seed_speed = s.seed_speed
        self._w = buffer.width()
        self._h = buffer.height()

        n = s.num_seeds
        rng = self.np_rng
        self._seeds = np.column_stack(
            [
                rng.uniform(0, self._w, n),
                rng.uniform(0, self._h, n),
                rng.uniform(-0.4, 0.4, n),  # vx
                rng.uniform(-0.2, 0.2, n),  # vy
            ]
        )

        cols = np.arange(self._w)
        rows = np.arange(self._h)
        self._X, self._Y = np.meshgrid(cols, rows)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self.buffer.clear_buffer(val=self.background)

        # Move seeds and bounce off edges
        self._seeds[:, 0] += self._seeds[:, 2] * self.seed_speed
        self._seeds[:, 1] += self._seeds[:, 3] * self.seed_speed
        for i in range(len(self._seeds)):
            if not (0 <= self._seeds[i, 0] < self._w):
                self._seeds[i, 2] *= -1
                self._seeds[i, 0] = float(np.clip(self._seeds[i, 0], 0, self._w - 1))
            if not (0 <= self._seeds[i, 1] < self._h):
                self._seeds[i, 3] *= -1
                self._seeds[i, 1] = float(np.clip(self._seeds[i, 1], 0, self._h - 1))

        sx, sy = self._seeds[:, 0], self._seeds[:, 1]

        # Assign each pixel to its nearest seed
        min_d = np.full((self._h, self._w), np.inf)
        nearest = np.zeros((self._h, self._w), dtype=np.int8)
        for i in range(len(self._seeds)):
            d = (self._X - sx[i]) ** 2 + ((self._Y - sy[i]) * 2) ** 2
            closer = d < min_d
            min_d[closer] = d[closer]
            nearest[closer] = i

        # Pre-build one coloured char per seed
        chars = []
        for i in range(len(self._seeds)):
            ratio = i / max(1, len(self._seeds) - 1)
            color = _heat(ratio) if self.color else None
            chars.append(bc(self.char, color=color) if color is not None else self.char)

        for r in range(self._h):
            for c in range(self._w):
                self.buffer.put_char(c, r, chars[int(nearest[r, c])])

        # Highlight each seed with a bright marker
        for i in range(len(self._seeds)):
            x, y = int(sx[i]), int(sy[i])
            if 0 <= x < self._w and 0 <= y < self._h:
                color = 226 if self.color else None
                self.buffer.put_char(x, y, bc("*", color=color) if color else "*")
