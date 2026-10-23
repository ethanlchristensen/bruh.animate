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

from ..bruhutil import LIFE_COLORS, Buffer
from .noise_effect import NoiseEffect
from .settings import StarSettings


class StarEffect(NoiseEffect):
    """
    A blinking star effect — a NoiseEffect with a predefined intensity and star characters.
    """

    def __init__(self, buffer: Buffer, background: str, settings: StarSettings = None):
        """
        Initializes the StarEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string for the background.
            settings (StarSettings, optional): Configuration for the star effect. Defaults to None.
        """
        super(StarEffect, self).__init__(buffer, background)
        s = settings or StarSettings()

        self.stars = f"{background * (100 // self.background_length)}.*+"
        self.stars_length = len(self.stars)
        self.color_type = s.color_type

    def set_color_type(self, color_type: str):
        """
        Updates the color type used for star rendering.

        Args:
            color_type (str): The color palette key to use.
        """
        self.color_type = color_type

    def set_background(self, background: str):
        """
        Updates the background character and rebuilds the star character set.

        Args:
            background (str): The new background character or string.
        """
        self.background = background
        self.background_length = len(background)
        self.stars = f"{background * (100 // self.background_length)}.*+"
        self.stars_length = len(self.stars)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                if random.random() < self.intensity:
                    self.buffer.put_char(
                        x,
                        y,
                        bruhcolored(
                            self.stars[random.randint(0, self.stars_length - 1)],
                            color=LIFE_COLORS[self.color_type][
                                random.randint(0, len(LIFE_COLORS[self.color_type]) - 1)
                            ],
                        ).colored,
                    )
