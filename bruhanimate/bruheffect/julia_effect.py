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

from ..bruhutil.bruhffer import Buffer
from ._resize import raster
from .base_effect import BaseEffect


class JuliaEffect(BaseEffect):
    """
    Class for generating a julia effect.
    """

    def __init__(self, buffer: Buffer, background: str):
        """
        Initializes the julia effect with a buffer and a background string.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): character or string to use as the background.
        """
        super(JuliaEffect, self).__init__(buffer, background)
        self.ascii_chars = "@%#*+=-:. "
        self.x_min, self.x_max = -1.5, 1.5
        self.y_min, self.y_max = -1, 1
        self.max_iter = 20
        self.tick = 0
        self.tick_delta = 1
        self.max_tick = 100
        self.min_tick = -200

    def update_tick(self):
        """
        Updates the current tick value and modifies the tick delta.

        The tick value is adjusted by the tick delta, which flips its sign
        when the tick reaches the boundaries defined by max_tick and min_tick.
        This ensures oscillation of the tick value within a specified range.
        """
        if self.tick >= self.max_tick:
            self.tick_delta = -1
        elif self.tick <= self.min_tick:
            self.tick_delta = 1
        self.tick += self.tick_delta

    def julia(self, c):
        """
        Computes the Julia set for a given complex parameter.

        Args:
            c (complex): A complex number used as a constant in the Julia set formula.

        Returns:
            np.ndarray: A 2D numpy array with values normalized to range [0, 1],
                        representing the iterative depth of each point in the set.
        """
        x_range = np.linspace(self.x_min, self.x_max, self.buffer.width())
        y_range = np.linspace(self.y_min, self.y_max, self.buffer.height())
        result = np.empty((self.buffer.height(), self.buffer.width()), dtype="float32")
        for i in range(self.buffer.width()):
            for j in range(self.buffer.height()):
                z = complex(x_range[i], y_range[j])
                iteration = 0
                while abs(z) < 2 and iteration < self.max_iter:
                    z = z * z + c
                    iteration += 1
                result[j, i] = iteration / self.max_iter
        return result

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        buffer = self.julia(complex(0.355 + 0.01 * self.tick, 0.355))
        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                self.buffer.put_char(
                    x,
                    y,
                    self.ascii_chars[int(buffer[y][x] * (len(self.ascii_chars) - 1))],
                )
        self.update_tick()

    def resize(self, size: tuple[int, int]) -> None:
        """Retain visible cells and expand the simulation raster without ticking."""
        self.buffer = raster(self.buffer, size, self.background)
        super().resize(size)
