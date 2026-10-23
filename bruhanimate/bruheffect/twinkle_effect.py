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
from .base_effect import BaseEffect
from .settings import TwinkleSettings


class TWINKLE_SPEC:
    """
    A single twinkle character that cycles through brightness levels.
    """

    def __init__(self, char: chr, value: int):
        """
        Initializes the twinkle character.

        Args:
            char (chr): Character to display.
            value (int): Initial brightness index (0–23).
        """
        self.char = char
        self.value = value
        self.fade = bruhcolored(self.char, TWINKLE_COLORS[self.value])
        self.mode = random.choice([1, -1])

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
        new = TWINKLE_SPEC(self.char, self.value)
        new.mode = self.mode
        return new


class TwinkleEffect(BaseEffect):
    """
    A twinkling star-like effect where characters pulse in brightness.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: TwinkleSettings = None
    ):
        """
        Initializes the TwinkleEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (TwinkleSettings, optional): Configuration for the effect. Defaults to None.
        """
        super(TwinkleEffect, self).__init__(buffer, background)
        s = settings or TwinkleSettings()
        self.density = s.density
        self.twinkle_chars = s.twinkle_chars
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
        Sets the characters used for the twinkle effect.

        Args:
            twinkle_chars (list[str]): List of characters to randomly assign to twinkle positions.
        """
        if isinstance(twinkle_chars, list):
            self.twinkle_chars = twinkle_chars
            self._set_specs()

    def _set_specs(self):
        self.specs = []
        self.buffer.clear_buffer()
        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                if random.random() < self.density:
                    spec = TWINKLE_SPEC(
                        random.choice(self.twinkle_chars), random.randint(0, 23)
                    )
                    self.buffer.put_char(x, y, spec)
                    self.specs.append((x, y))

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for x, y in self.specs:
            spec = self.buffer.get_char(x, y)
            self.buffer.put_char(x, y, spec.next().copy())
            del spec
