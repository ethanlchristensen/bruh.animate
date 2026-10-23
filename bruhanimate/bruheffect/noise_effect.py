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

from bruhcolor import bruhcolored

from ..bruhutil import Buffer
from .base_effect import BaseEffect
from .settings import NoiseSettings, validated_settings


class NoiseEffect(BaseEffect):
    """
    A noise effect that adds random pixels to the screen with a specified intensity.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: NoiseSettings | None = None
    ):
        """
        Initializes the NoiseEffect class.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string for background.
            settings (NoiseSettings, optional): Configuration for the noise effect. Defaults to None.
        """
        s = validated_settings(settings, NoiseSettings)
        super(NoiseEffect, self).__init__(buffer, background, seed=s.seed)

        self.intensity = s.intensity / 1000
        self.color = s.color
        self.characters = True

        self.noise = " !@#$%^&*()_+1234567890-=~`qazwsxedcrfvtgbyhnujmik,ol.p;/[']\\QAZXSWEDCVFRTGBNHYUJM<KIOL>?:P{\"}|"
        self.noise_length = len(self.noise)

    def set_intensity(self, intensity: int):
        """
        Updates the intensity of the effect.

        Args:
            intensity (int): New intensity value between 1 and 999.
        """
        self.intensity = (
            intensity / 1000 if intensity and 1 <= intensity <= 999 else 200 / 1000
        )

    def set_color(self, color: bool, characters: bool = True):
        """
        Updates the color and character rendering mode.

        Args:
            color (bool): Whether to render with color.
            characters (bool, optional): Whether to render noise characters or background blocks. Defaults to True.
        """
        self.color = color
        self.characters = characters

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        if self.color:
            for y in range(self.buffer.height()):
                for x in range(self.buffer.width()):
                    if self.rng.random() < self.intensity:
                        if self.characters:
                            self.buffer.put_char(
                                x,
                                y,
                                bruhcolored(
                                    self.noise[
                                        self.rng.randint(0, self.noise_length - 1)
                                    ],
                                    on_color=self.rng.randint(0, 255),
                                ).colored,
                            )
                        else:
                            self.buffer.put_char(
                                x,
                                y,
                                bruhcolored(
                                    " ", on_color=self.rng.randint(0, 255)
                                ).colored,
                            )
        else:
            for y in range(self.buffer.height()):
                for x in range(self.buffer.width()):
                    if self.rng.random() < self.intensity:
                        self.buffer.put_char(
                            x, y, self.noise[self.rng.randint(0, self.noise_length - 1)]
                        )
