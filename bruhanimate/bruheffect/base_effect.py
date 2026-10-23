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

import random
from abc import ABC, abstractmethod

import numpy as np

from ..bruhutil.bruhffer import Buffer
from ..resize import _size


class BaseEffect(ABC):
    """A simulation with a persistent private raster and explicit resource ownership.

    Built-in simulations advance one step per update. Set updates_per_second on
    the Player to choose their speed independently of presentation FPS. Custom
    effects can use dt (seconds) for continuous motion instead.
    """

    def __init__(self, buffer: Buffer, background: str, *, seed: int | None = None):
        """
        Base class for all effects.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): character or string to use for the background.
            seed: Non-negative integer for independent Python and NumPy random
                streams. None uses fresh entropy. Global RNG state is untouched.
        """
        if seed is not None:
            if type(seed) is not int:
                raise TypeError("seed must be an integer or None")
            if seed < 0:
                raise ValueError("seed must be non-negative")
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.buffer = buffer
        self.background = background
        self.background_length = len(background)
        self._viewport: tuple[int, int] | None = None
        self._started = False

    def start(self) -> None:
        """Acquire runtime resources. Construction must not open devices or threads.

        Players and scenes call this before the first update and own cleanup
        for the duration of playback. Overrides should tolerate repeated calls.
        """
        self._started = True

    def stop(self) -> None:
        """Release runtime resources; safe to call before start or more than once."""
        self._started = False

    def close(self) -> None:
        """Release resources through stop(); safe before start and on repeats."""
        self.stop()

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance simulation by one tick; dt is the tick duration in seconds."""

    def resize(self, size: tuple[int, int]) -> None:
        """Change the drawing viewport, retaining the original simulation raster.

        Shrinking clips from the bottom/right; growing reveals the original
        raster again. Cells beyond it remain transparent to the owner. Random
        streams, resource handles and simulation coordinates are unchanged.
        Subclasses can override this typed hook to adapt simulation arrays and
        repaint the private raster at the current tick, then call super().resize.
        Built-in adapters use this contract; draw must still never advance time.
        """
        _size(size)
        self._viewport = size

    def draw(self, buffer: Buffer) -> None:
        """Copy the latest raster without advancing or sharing mutable cells."""
        if self._viewport is None:
            buffer._validate_dimensions(self.buffer)
        elif (buffer.width(), buffer.height()) != self._viewport:
            raise ValueError("Drawing buffer must match the resized viewport")
        for y in range(min(buffer.height(), self.buffer.height())):
            for x in range(min(buffer.width(), self.buffer.width())):
                cell = self.buffer.buffer[y][x]
                if cell is not None:
                    buffer.buffer[y][x] = str(cell)
