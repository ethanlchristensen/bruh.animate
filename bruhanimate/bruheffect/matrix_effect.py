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

import string

from bruhcolor import bruhcolored

from ..bruhutil import Buffer
from .base_effect import BaseEffect
from .settings import MatrixSettings, validated_settings


class MatrixEffect(BaseEffect):
    """
    Effect to mimic the classic cascading random-character terminal background.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: MatrixSettings | None = None
    ):
        """
        Initializes the MatrixEffect.

        Args:
            buffer (Buffer): Effect buffer to push changes to.
            background (str): Character or string used for the background.
            settings (MatrixSettings, optional): Configuration for the matrix effect. Defaults to None.
        """
        s = validated_settings(settings, MatrixSettings)
        super(MatrixEffect, self).__init__(buffer, background, seed=s.seed)

        self.__character_choices = (
            string.ascii_letters + "1234567890!@#$%^&*()_+-=<>,.:\";'{}[]?/"
        )
        self.__character_halt_range = s.character_halt_range
        self.__color_halt_range = s.color_halt_range
        self.__character_randomness_one = s.character_randomness_one
        self.__character_randomness_two = s.character_randomness_two
        self.__color_randomness = s.color_randomness
        self.__gradient_length = s.gradient_length

        self.__base_gradient = [
            232,
            233,
            234,
            235,
            236,
            237,
            238,
            239,
            240,
            241,
            242,
            243,
            244,
            245,
            246,
            247,
            248,
            249,
            250,
            251,
            252,
            253,
            254,
            255,
        ]
        self.__gradient = [
            color
            for color in self.__base_gradient
            for _ in range(self.__gradient_length)
        ]
        self.__character_halts = [
            self.rng.randint(
                self.__character_halt_range[0], self.__character_halt_range[1]
            )
            for _ in range(self.buffer.height())
        ]
        self.__color_halts = [
            self.rng.randint(self.__color_halt_range[0], self.__color_halt_range[1])
            for _ in range(self.buffer.height())
        ]
        self.__character_ticks = [0 for _ in range(self.buffer.height())]
        self.__color_ticks = [0 for _ in range(self.buffer.height())]
        self.__buffer_characters = [
            [" " for _ in range(self.buffer.width())]
            for _ in range(self.buffer.height())
        ]
        self._tick = 0

    def set_properties(
        self,
        character_halt_range: tuple = (1, 2),
        color_halt_range: tuple = (1, 2),
        character_randomness_one: float = 0.70,
        character_randomness_two: float = 0.60,
        color_randomness: float = 0.50,
        gradient_length: int = 1,
    ):
        """
        Updates the matrix effect properties.

        Args:
            character_halt_range (tuple, optional): Frame range between character updates. Defaults to (1, 2).
            color_halt_range (tuple, optional): Frame range between color updates. Defaults to (1, 2).
            character_randomness_one (float, optional): Probability of a row updating characters. Defaults to 0.70.
            character_randomness_two (float, optional): Probability of each cell in a row updating. Defaults to 0.60.
            color_randomness (float, optional): Probability of a row shifting its color gradient. Defaults to 0.50.
            gradient_length (int, optional): How many times each color is repeated in the gradient. Defaults to 1.
        """
        self.__character_randomness_one = character_randomness_one
        self.__character_randomness_two = character_randomness_two
        self.__color_randomness = color_randomness
        self.__character_halt_range = character_halt_range
        self.__color_halt_range = color_halt_range
        self.__gradient_length = gradient_length
        self.__gradient = [
            color
            for color in self.__base_gradient
            for _ in range(self.__gradient_length)
        ]
        self.__character_halts = [
            self.rng.randint(
                self.__character_halt_range[0], self.__character_halt_range[1]
            )
            for _ in range(self.buffer.height())
        ]
        self.__color_halts = [
            self.rng.randint(self.__color_halt_range[0], self.__color_halt_range[1])
            for _ in range(self.buffer.height())
        ]

    def set_gradient(self, gradient: list[int]):
        """
        Replaces the base color gradient.

        Args:
            gradient (list[int]): List of 256-color indices to use.
        """
        self.__base_gradient = gradient
        self.__gradient = [
            color
            for color in self.__base_gradient
            for _ in range(self.__gradient_length)
        ]

    def get_gradient(self) -> list[int]:
        """
        Returns the current base gradient.

        Returns:
            list[int]: The current base gradient.
        """
        return self.__base_gradient

    def __initialize_buffer(self):
        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                self.__buffer_characters[y][x] = self.rng.choice(
                    self.__character_choices
                )
            for x in range(self.buffer.width()):
                self.buffer.put_char(
                    x,
                    y,
                    bruhcolored(
                        self.__buffer_characters[y][x],
                        self.__gradient[x % len(self.__gradient)],
                    ).colored,
                )

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        tick = self._tick
        self._tick += 1
        if tick == 0:
            self.__initialize_buffer()
        else:
            for y in range(self.buffer.height()):
                if (
                    tick % self.__character_halts[y] == 0
                    and self.rng.random() < self.__character_randomness_one
                ):
                    self.__character_ticks[y] += 1
                    for x in range(self.buffer.width()):
                        if self.rng.random() < self.__character_randomness_two:
                            self.__buffer_characters[y][x] = self.rng.choice(
                                self.__character_choices
                            )

                if (
                    tick % self.__color_halts[y] == 0
                    and self.rng.random() < self.__color_randomness
                ):
                    self.__color_ticks[y] += 1
                    for x in range(self.buffer.width()):
                        self.buffer.put_char(
                            x,
                            y,
                            bruhcolored(
                                self.__buffer_characters[y][x],
                                color=self.__gradient[
                                    (x - self.__color_ticks[y]) % len(self.__gradient)
                                ],
                            ),
                        )
