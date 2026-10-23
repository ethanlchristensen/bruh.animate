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
from .settings import SandSettings, validated_settings


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


class SandEffect(BaseEffect):
    """
    Falling-sand cellular automaton.

    Particles spawn randomly at the top of the screen and fall downward,
    cascading diagonally when blocked. Color indicates height — hotter
    at the top, cooler toward the bottom. Particles drain from the
    bottom row to keep the simulation flowing indefinitely.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: SandSettings | None = None
    ):
        s = validated_settings(settings, SandSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.color = s.color
        self.char = s.char
        self.spawn_rate = max(0.0, min(1.0, s.spawn_rate))
        self._w = buffer.width()
        self._h = buffer.height()
        self._grid = np.zeros((self._h, self._w), dtype=np.uint8)

    def set_spawn_rate(self, rate: float):
        """Set the per-column probability of spawning a new particle each frame (0–1)."""
        self.spawn_rate = max(0.0, min(1.0, rate))

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self.buffer.clear_buffer(val=self.background)

        # Drain bottom row so the simulation never stalls
        self._grid[self._h - 1, :] = 0

        # Spawn new particles at the top
        for col in range(self._w):
            if self.rng.random() < self.spawn_rate and self._grid[0, col] == 0:
                self._grid[0, col] = 1

        # Update: process non-empty cells bottom-to-top
        occ_r, occ_c = np.where(self._grid > 0)
        if len(occ_r):
            order = np.argsort(-occ_r)
            for idx in order:
                r, c = int(occ_r[idx]), int(occ_c[idx])
                if r >= self._h - 1 or self._grid[r, c] == 0:
                    continue
                if self._grid[r + 1, c] == 0:
                    self._grid[r, c] = 0
                    self._grid[r + 1, c] = 1
                else:
                    dirs = (-1, 1) if self.rng.random() < 0.5 else (1, -1)
                    for d in dirs:
                        nc = c + d
                        if 0 <= nc < self._w and self._grid[r + 1, nc] == 0:
                            self._grid[r, c] = 0
                            self._grid[r + 1, nc] = 1
                            break

        # Draw
        lit_r, lit_c = np.where(self._grid > 0)
        for r, c in zip(lit_r, lit_c):
            ratio = 1.0 - float(r) / self._h
            color = _heat(ratio) if self.color else None
            ch = bc(self.char, color=color) if color is not None else self.char
            self.buffer.put_char(int(c), int(r), ch)
