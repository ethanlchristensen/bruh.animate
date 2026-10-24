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
from ._resize import raster
from .base_effect import BaseEffect
from .settings import BoidsSettings, validated_settings


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


class BoidsEffect(BaseEffect):
    """
    Reynolds flocking simulation.

    Each boid obeys three rules:
    - **Separation** — steer away from close neighbours
    - **Alignment**  — match average velocity of nearby flock
    - **Cohesion**   — move toward average position of nearby flock

    Boids wrap around screen edges. Speed is colour-mapped hot (fast) to
    cool (slow) when *color* is enabled.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: BoidsSettings | None = None
    ):
        s = validated_settings(settings, BoidsSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.color = s.color
        self.char = s.char
        self.max_speed = s.max_speed
        self.perception = s.perception
        self._w = buffer.width()
        self._h = buffer.height()

        rng = self.np_rng
        n = s.num_boids
        self._pos = np.column_stack(
            [
                rng.uniform(0, self._w, n),
                rng.uniform(0, self._h, n),
            ]
        )
        self._vel = np.column_stack(
            [
                rng.uniform(-0.8, 0.8, n),
                rng.uniform(-0.4, 0.4, n),
            ]
        )

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        pos = self._pos
        vel = self._vel

        diff = pos[:, np.newaxis, :] - pos[np.newaxis, :, :]
        dist = np.sqrt((diff**2).sum(axis=2))
        np.fill_diagonal(dist, np.inf)

        nbr = dist < self.perception
        close = dist < self.perception * 0.28
        has_nbr = nbr.any(axis=1, keepdims=True)
        n_nbr = nbr.sum(axis=1, keepdims=True).clip(1, None)

        sep = np.where(close[:, :, np.newaxis], diff, 0.0).sum(axis=1) * 0.12
        vel_sum = np.where(nbr[:, :, np.newaxis], vel[np.newaxis], 0.0).sum(axis=1)
        align = np.where(has_nbr, (vel_sum / n_nbr - vel) * 0.05, 0.0)
        pos_sum = np.where(nbr[:, :, np.newaxis], pos[np.newaxis], 0.0).sum(axis=1)
        cohesion = np.where(has_nbr, (pos_sum / n_nbr - pos) * 0.003, 0.0)

        new_vel = vel + sep + align + cohesion
        new_vel += self.np_rng.uniform(-0.02, 0.02, new_vel.shape)

        speeds = np.linalg.norm(new_vel, axis=1, keepdims=True).clip(1e-8)
        new_vel = np.where(
            speeds > self.max_speed, new_vel / speeds * self.max_speed, new_vel
        )
        new_vel = np.where(speeds < 0.3, new_vel / speeds * 0.3, new_vel)

        new_pos = (pos + new_vel) % np.array([[self._w, self._h]])
        self._pos = new_pos
        self._vel = new_vel

        self._paint()

    def _paint(self) -> None:
        self.buffer.clear_buffer(val=self.background)
        new_pos, new_vel = self._pos, self._vel
        xs = new_pos[:, 0].astype(int)
        ys = new_pos[:, 1].astype(int)
        spd_norm = (np.linalg.norm(new_vel, axis=1) / max(self.max_speed, 1e-8)).clip(
            0, 1
        )
        valid = (xs >= 0) & (xs < self._w) & (ys >= 0) & (ys < self._h)

        for i in np.where(valid)[0]:
            color = _heat(float(spd_norm[i])) if self.color else None
            ch = bc(self.char, color=color) if color is not None else self.char
            self.buffer.put_char(int(xs[i]), int(ys[i]), ch)

    def resize(self, size: tuple[int, int]) -> None:
        """Wrap positions into the new bounds, preserving flock size and velocities."""
        self.buffer = raster(self.buffer, size, self.background)
        self._w, self._h = size
        self._pos %= np.array([[self._w, self._h]])
        self._paint()
        super().resize(size)
