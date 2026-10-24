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

import numpy as np
from bruhcolor import bruhcolored

from ..bruhutil import GREY_SCALES, PLASMA_COLORS, Buffer
from ..resize import _size
from .base_effect import BaseEffect
from .settings import PlasmaSettings, validated_settings


class PlasmaEffect(BaseEffect):
    """
    Class to generate an animated plasma effect.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: PlasmaSettings | None = None
    ):
        """
        Initializes the PlasmaEffect class.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (PlasmaSettings, optional): Configuration for the plasma effect. Defaults to None.
        """
        s = validated_settings(settings, PlasmaSettings)
        super(PlasmaEffect, self).__init__(buffer, background, seed=s.seed)
        self.show_info = s.show_info
        self.random_colors = s.random_colors
        self.color = s.color
        self.characters = s.characters
        self.scale = self.rng.choice(GREY_SCALES)
        self.colors = PLASMA_COLORS[len(self.scale)][0]
        self.t = 0
        self.vals = [self.rng.randint(1, 100) for _ in range(4)]
        self._colored_cache = None
        self._geometry_key = None

    def _build_cache(self):
        if self.color:
            if self.characters:
                self._colored_cache = [
                    bruhcolored(self.scale[i], color=self.colors[i]).colored
                    for i in range(len(self.scale))
                ]
            else:
                self._colored_cache = [
                    f"\x1b[48;5;{self.colors[i]}m \x1b[0m"
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
        self.scale = self.rng.choice([s for s in GREY_SCALES if len(s) == size])
        if not self.random_colors:
            self.colors = self.rng.choice(PLASMA_COLORS[size])
        else:
            self.colors = [self.rng.randint(0, 255) for _ in range(len(self.scale))]
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
            self.colors = [self.rng.randint(0, 255) for _ in range(len(self.scale))]
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
        self.vals = [self.rng.randint(1, 50) for _ in range(4)]

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        self.t += 1
        self._paint_frame()

    def resize(self, size: tuple[int, int]) -> None:
        """Fill a new (width, height) at the current phase, without random draws.

        Frequency values, palette, settings and animation time are retained.
        Wave anchors follow the new dimensions. No update/start/close is called.
        """
        _size(size)
        if size != (self.buffer.width(), self.buffer.height()):
            self.buffer = Buffer(size[1], size[0])
            self._paint_frame()
        super().resize(size)

    def _paint_frame(self) -> None:
        """Paint vectorized waves, caching static geometry until size/values change.

        Palette boundaries use the scalar formula to preserve visible cells.
        This runs during update/resize; draw remains a read-only raster copy.
        """
        if self._colored_cache is None:
            self._build_cache()

        cache = self._colored_cache
        scale_max = len(self.scale) - 1
        width, height = self.buffer.width(), self.buffer.height()
        key = (width, height, tuple(self.vals))
        if key != self._geometry_key:
            self._x = np.arange(width, dtype=float)[None, :]
            self._y = np.arange(height, dtype=float)[:, None]
            self._static_waves = tuple(
                np.sin(
                    np.sqrt(
                        (self._x - width * a) ** 2 + 4 * (self._y - height * b) ** 2
                    )
                    * math.pi
                    / n
                )
                for a, b, n in (
                    (1 / 8, 1 / 5, self.vals[1]),
                    (3 / 4, 4 / 5, self.vals[3]),
                )
            )
            self._geometry_key = key
        t3 = self.t / 3.0
        first = np.sin(
            np.sqrt(
                (self._x + t3 - width * (1 / 4)) ** 2
                + 4 * (self._y - height * (1 / 3)) ** 2
            )
            * math.pi
            / self.vals[0]
        )
        third = np.sin(
            np.sqrt(
                (self._x - width * (1 / 2)) ** 2
                + 4 * (self._y + t3 - height * (1 / 5)) ** 2
            )
            * math.pi
            / self.vals[2]
        )
        values = (
            np.abs(first + self._static_waves[0] + third + self._static_waves[1])
            / 4.0
            * scale_max
        )
        indices = values.astype(np.intp)
        # NumPy/libm can differ by a few ulps. Resolve palette boundaries with
        # the scalar formula so optimization does not change visible cells.
        ys, xs = np.nonzero(np.abs(values - np.rint(values)) < 1e-10)
        for y, x in zip(ys.tolist(), xs.tolist()):
            value = (
                abs(
                    self._wave(x + t3, y, 1 / 4, 1 / 3, self.vals[0])
                    + self._wave(x, y, 1 / 8, 1 / 5, self.vals[1])
                    + self._wave(x, y + t3, 1 / 2, 1 / 5, self.vals[2])
                    + self._wave(x, y, 3 / 4, 4 / 5, self.vals[3])
                )
                / 4.0
            )
            indices[y, x] = int(scale_max * value)
        self.buffer.buffer = np.asarray(cache, dtype=object)[indices].tolist()

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
