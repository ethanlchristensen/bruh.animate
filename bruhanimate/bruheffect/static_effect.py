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

from ..bruhutil.bruhffer import Buffer
from .base_effect import BaseEffect


class StaticEffect(BaseEffect):
    """
    Class for generating a static background.
    """

    def __init__(self, buffer: Buffer, background: str):
        """
        Initializes the static effect with a buffer and a background string.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): character or string to use as the background.
        """
        super(StaticEffect, self).__init__(buffer, background)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for y in range(self.buffer.height()):
            self.buffer.put_at(
                0,
                y,
                self.background
                * (
                    self.buffer.width() // self.background_length
                    + self.background_length
                ),
            )
