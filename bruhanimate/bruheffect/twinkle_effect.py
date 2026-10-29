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

from bruhcolor import bruhcolored

from ..bruhutil import TWINKLE_COLORS, Buffer
from ._resize import raster
from .base_effect import BaseEffect
from .settings import TwinkleSettings, validated_settings


class TWINKLE_SPEC:
    """
    A single twinkle character that cycles through brightness levels.
    """

    def __init__(
        self,
        char: str,
        value: int,
        *,
        rng: random.Random | None = None,
        mode: int | None = None,
    ):
        """
        Initializes the twinkle character.

        Args:
            char (chr): Character to display.
            value (int): Initial brightness index (0–23).
        """
        self.char = char
        self.value = value
        self.fade = bruhcolored(self.char, TWINKLE_COLORS[self.value])
        self.mode = (
            mode
            if mode is not None
            else (rng if rng is not None else random.Random()).choice([1, -1])
        )

    def __str__(self):
        return self.fade.colored

    def __repr__(self):
        return self.fade.colored

    def __len__(self):
        return 1

    def next(self):
        """
        Advances the brightness by one step and returns self.
        """
        if self.value >= 23:
            self.mode = -1
        elif self.value <= 0:
            self.mode = 1
        self.value += self.mode
        self.fade = bruhcolored(self.char, TWINKLE_COLORS[self.value])
        return self

    def copy(self):
        """
        Returns a copy of this TWINKLE_SPEC.

        Returns:
            TWINKLE_SPEC: Copy with the same char, value, and mode.
        """
        new = TWINKLE_SPEC(self.char, self.value, mode=self.mode)
        new.mode = self.mode
        return new


class TwinkleEffect(BaseEffect):
    """
    A twinkling star-like effect where characters pulse in brightness.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: TwinkleSettings | None = None
    ):
        """
        Initializes the TwinkleEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (TwinkleSettings, optional): Configuration for the effect. Defaults to None.
        """
        s = validated_settings(settings, TwinkleSettings)
        super(TwinkleEffect, self).__init__(buffer, background, seed=s.seed)
        self.density = s.density
        self.twinkle_chars = list(s.twinkle_chars)
        self.specs = []
        self._set_specs()

    def set_density(self, density: float):
        """
        Sets the density of twinkling characters.

        Args:
            density (float): Fraction of cells that twinkle, between 0 and 1.
        """
        if isinstance(density, float) and 0 <= density <= 1:
            self.density = density
            self._set_specs()

    def set_twinkle_chars(self, twinkle_chars: list[str]):
        """
        Validate and copy characters before rebuilding the twinkle field.

        Invalid input leaves the current field and random stream unchanged.

        Args:
            twinkle_chars (list[str]): List of characters to randomly assign to twinkle positions.
        """
        settings = TwinkleSettings(twinkle_chars=twinkle_chars)
        self.twinkle_chars = list(settings.twinkle_chars)
        self._set_specs()

    def _set_specs(self):
        self.specs = []
        self._pending = set()
        self.buffer.clear_buffer()
        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                if self.rng.random() < self.density:
                    spec = TWINKLE_SPEC(
                        self.rng.choice(self.twinkle_chars),
                        self.rng.randint(0, 23),
                        rng=self.rng,
                    )
                    self.buffer.put_char(x, y, spec)
                    self.specs.append((x, y))

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for x, y in sorted(self._pending, key=lambda cell: (cell[1], cell[0])):
            if self.rng.random() < self.density:
                self.buffer.put_char(
                    x,
                    y,
                    TWINKLE_SPEC(
                        self.rng.choice(self.twinkle_chars),
                        self.rng.randint(0, 23),
                        rng=self.rng,
                    ),
                )
                self.specs.append((x, y))
        self._pending.clear()
        for x, y in self.specs:
            spec = self.buffer.get_char(x, y)
            self.buffer.put_char(x, y, spec.next().copy())
            del spec

    def resize(self, size: tuple[int, int]) -> None:
        """Retain twinkle phases; seed newly exposed cells on the next update."""
        old_width, old_height = self.buffer.width(), self.buffer.height()
        resized = raster(self.buffer, size, self.background)
        width, height = size
        self.specs = [(x, y) for x, y in self.specs if x < width and y < height]
        self._pending = {(x, y) for x, y in self._pending if x < width and y < height}
        self._pending.update(
            (x, y)
            for y in range(height)
            for x in range(width)
            if x >= old_width or y >= old_height
        )
        self.buffer = resized
        super().resize(size)
