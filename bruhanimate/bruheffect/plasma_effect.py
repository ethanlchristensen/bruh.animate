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
import random

from bruhcolor import bruhcolored

from ..bruhutil import GREY_SCALES, PLASMA_COLORS, Buffer
from .base_effect import BaseEffect
from .settings import PlasmaSettings


class PlasmaEffect(BaseEffect):
    """
    Class to generate an animated plasma effect.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: PlasmaSettings = None
    ):
        """
        Initializes the PlasmaEffect class.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (PlasmaSettings, optional): Configuration for the plasma effect. Defaults to None.
        """
        super(PlasmaEffect, self).__init__(buffer, background)
        s = settings or PlasmaSettings()
        self.show_info = s.show_info
        self.random_colors = s.random_colors
        self.color = s.color
        self.characters = s.characters
        self.scale = random.choice(GREY_SCALES)
        self.colors = PLASMA_COLORS[len(self.scale)][0]
        self.t = 0
        self.vals = [random.randint(1, 100) for _ in range(4)]
        self._colored_cache = None

    def _build_cache(self):
        if self.color:
            if self.characters:
                self._colored_cache = [
                    bruhcolored(self.scale[i], color=self.colors[i]).colored
                    for i in range(len(self.scale))
                ]
            else:
                self._colored_cache = [
                    bruhcolored(" ", on_color=self.colors[i]).colored
                    for i in range(len(self.scale))
                ]
        else:
            self._colored_cache = list(self.scale)

    def set_show_info(self, visible: bool):
        """
        Toggles visibility of debug info overlay.

        Args:
            visible (bool): Whether to show the info overlay.
        """
        self.show_info = visible

    def set_grey_scale_size(self, size: int):
        """
        Sets the grey scale size, which controls detail level.

        Args:
            size (int): Must be 8, 10, or 16.

        Raises:
            ValueError: If size is not one of the supported values.
        """
        if size not in [8, 10, 16]:
            raise ValueError(
                f"only 8, 10, and 16 are supported grey scale sizes, got {size}"
            )
        self.scale = random.choice([s for s in GREY_SCALES if len(s) == size])
        if not self.random_colors:
            self.colors = random.choice(PLASMA_COLORS[size])
        else:
            self.colors = [random.randint(0, 255) for _ in range(len(self.scale))]
        self._colored_cache = None

    def set_color_properties(
        self, color: bool, characters: bool = True, random_colors: bool = False
    ):
        """
        Configures color rendering. random_colors overrides the palette.

        Args:
            color (bool): Whether to render with color.
            characters (bool, optional): Whether to render scale characters. Defaults to True.
            random_colors (bool, optional): Whether to use a random color palette. Defaults to False.
        """
        self.color = color
        self.random_colors = random_colors
        self.characters = characters
        if not random_colors:
            self.colors = PLASMA_COLORS[len(self.scale)][0]
        else:
            self.colors = [random.randint(0, 255) for _ in range(len(self.scale))]
        self._colored_cache = None

    def set_colors(self, colors: list[int]):
        """
        Sets a custom color palette. Has no effect if random_colors is enabled.

        Args:
            colors (list[int]): List of 256-color indices, one per scale character.

        Raises:
            ValueError: If the number of colors does not match the scale length.
        """
        if self.random_colors:
            return
        if len(colors) != len(self.scale):
            raise ValueError(f"expected {len(self.scale)} colors, got {len(colors)}")
        self.colors = colors
        self._colored_cache = None

    def set_background(self, background: str):
        """
        Updates the background character or string.

        Args:
            background (str): Character or string to use as background.
        """
        self.background = background
        self.background_length = len(background)

    def set_plasma_values(self, a: int, b: int, c: int, d: int):
        """
        Sets the four plasma frequency values.

        Args:
            a (int): First frequency value.
            b (int): Second frequency value.
            c (int): Third frequency value.
            d (int): Fourth frequency value.
        """
        self.vals = [a, b, c, d]

    def shuffle_plasma_values(self):
        """
        Randomizes the four plasma frequency values.
        """
        self.vals = [random.randint(1, 50) for _ in range(4)]

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self.t += 1
        if self._colored_cache is None:
            self._build_cache()

        cache = self._colored_cache
        scale_max = len(self.scale) - 1
        t3 = self.t / 3.0

        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                value = (
                    abs(
                        self._wave(x + t3, y, 1 / 4, 1 / 3, self.vals[0])
                        + self._wave(x, y, 1 / 8, 1 / 5, self.vals[1])
                        + self._wave(x, y + t3, 1 / 2, 1 / 5, self.vals[2])
                        + self._wave(x, y, 3 / 4, 4 / 5, self.vals[3])
                    )
                    / 4.0
                )
                self.buffer.put_char(x, y, cache[int(scale_max * value)])

        if self.show_info:
            self.buffer.put_at(0, 0, f"COLORS: {' '.join(str(v) for v in self.colors)}")
            for i in range(1, 5):
                self.buffer.put_at(0, i, f"VAL {i}: {self.vals[i - 1]:>3d}")

    def _wave(self, x: float, y: float, a: float, b: float, n: float) -> float:
        """
        Sine wave radially projected from a point on the screen.

        Args:
            x (float): Horizontal position.
            y (float): Vertical position.
            a (float): Horizontal anchor fraction of screen width.
            b (float): Vertical anchor fraction of screen height.
            n (float): Frequency divisor.

        Returns:
            float: Sine value at (x, y).
        """
        return math.sin(
            math.sqrt(
                (x - self.buffer.width() * a) ** 2
                + 4 * (y - self.buffer.height() * b) ** 2
            )
            * math.pi
            / n
        )
