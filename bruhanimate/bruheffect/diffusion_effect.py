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
from .settings import DiffusionSettings, validated_settings


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


class DiffusionEffect(BaseEffect):
    """
    Gray-Scott reaction-diffusion simulation.

    Two virtual chemicals U and V interact according to the Gray-Scott
    model, producing organic-looking spots, stripes, and coral patterns
    that evolve continuously. Default parameters (f=0.055, k=0.062) sit
    in the coral/worm-pattern regime; adjust them to explore the full
    parameter space.

    Multiple simulation steps run per rendered frame so the pattern
    evolves fast enough to be visually interesting.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: DiffusionSettings | None = None
    ):
        s = validated_settings(settings, DiffusionSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.color = s.color
        self.char = s.char
        self.f = s.f
        self.k = s.k
        self.steps_per_frame = s.steps_per_frame

        h, w = buffer.height(), buffer.width()
        self._h, self._w = h, w

        self._U = np.ones((h, w), dtype=np.float32)
        self._V = np.zeros((h, w), dtype=np.float32)

        cy, cx = h // 2, w // 2
        r = max(2, min(h, w) // 6)
        self._U[cy - r : cy + r, cx - r : cx + r] = 0.50
        self._V[cy - r : cy + r, cx - r : cx + r] = 0.25

        rng = self.np_rng
        self._U = np.clip(
            self._U + rng.uniform(-0.02, 0.02, (h, w)).astype(np.float32), 0.0, 1.0
        )
        self._V = np.clip(
            self._V + rng.uniform(-0.02, 0.02, (h, w)).astype(np.float32), 0.0, 1.0
        )

    def set_parameters(self, f: float = None, k: float = None):
        """Update the feed (f) and/or kill (k) rate at runtime."""
        if f is not None:
            self.f = float(f)
        if k is not None:
            self.k = float(k)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self.buffer.clear_buffer(val=self.background)

        for _ in range(self.steps_per_frame):
            Lu = (
                np.roll(self._U, 1, 0)
                + np.roll(self._U, -1, 0)
                + np.roll(self._U, 1, 1)
                + np.roll(self._U, -1, 1)
                - 4 * self._U
            )
            Lv = (
                np.roll(self._V, 1, 0)
                + np.roll(self._V, -1, 0)
                + np.roll(self._V, 1, 1)
                + np.roll(self._V, -1, 1)
                - 4 * self._V
            )
            uvv = self._U * self._V * self._V
            self._U += 0.16 * Lu - uvv + self.f * (1.0 - self._U)
            self._V += 0.08 * Lv + uvv - (self.f + self.k) * self._V
        np.clip(self._U, 0.0, 1.0, out=self._U)
        np.clip(self._V, 0.0, 1.0, out=self._V)

        lit_r, lit_c = np.where(self._V > 0.08)
        mags = self._V[lit_r, lit_c]
        for i in range(len(lit_r)):
            color = _heat(float(mags[i])) if self.color else None
            ch = bc(self.char, color=color) if color is not None else self.char
            self.buffer.put_char(int(lit_c[i]), int(lit_r[i]), ch)
