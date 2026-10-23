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

from ..bruhutil import VALID_DIRECTIONS
from ..bruhutil.bruhffer import Buffer
from .base_effect import BaseEffect
from .settings import OffsetSettings, validated_settings


class OffsetEffect(BaseEffect):
    """
    Class for generating an offset-scrolling background.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: OffsetSettings | None = None
    ):
        """
        Initializes the OffsetEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (OffsetSettings, optional): Configuration for the offset effect. Defaults to None.
        """
        s = validated_settings(settings, OffsetSettings)
        super(OffsetEffect, self).__init__(buffer, background, seed=s.seed)
        self.direction = s.direction if s.direction in VALID_DIRECTIONS else "right"

    def set_direction(self, direction: str):
        """
        Updates the scroll direction.

        Args:
            direction (str): Direction to scroll ("left" or "right").
        """
        if direction in VALID_DIRECTIONS:
            self.direction = direction
            self.buffer.clear_buffer()

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for y in range(self.buffer.height()):
            row = (
                self.background[y % self.background_length :]
                + self.background[: y % self.background_length]
            ) * (self.buffer.width() // self.background_length + self.background_length)
            if self.direction == "right":
                self.buffer.put_at(0, y, row[::-1])
            else:
                self.buffer.put_at(0, y, row)
