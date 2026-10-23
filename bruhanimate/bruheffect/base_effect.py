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

from abc import ABC, abstractmethod

from ..bruhutil.bruhffer import Buffer


class BaseEffect(ABC):
    """A simulation with a persistent private raster and explicit resource ownership.

    Built-in simulations advance one step per update. Set updates_per_second on
    the Player to choose their speed independently of presentation FPS. Custom
    effects can use dt (seconds) for continuous motion instead.
    """

    def __init__(self, buffer: Buffer, background: str):
        """
        Base class for all effects.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): character or string to use for the background.
        """
        self.buffer = buffer
        self.background = background
        self.background_length = len(background)
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

    def draw(self, buffer: Buffer) -> None:
        """Copy the latest raster without advancing or sharing mutable cells."""
        buffer._validate_dimensions(self.buffer)
        for y, row in enumerate(self.buffer.buffer):
            target = buffer.buffer[y]
            buffer.buffer[y] = [
                target[x] if cell is None else str(cell) for x, cell in enumerate(row)
            ]
