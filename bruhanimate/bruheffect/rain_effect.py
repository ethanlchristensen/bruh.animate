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

from ..bruhutil import WIND_DIRECTIONS, Buffer
from ..resize import _size
from .base_effect import BaseEffect
from .settings import RainSettings, validated_settings


class RainEffect(BaseEffect):
    """
    Effect to simulate the look of rain.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: RainSettings | None = None
    ):
        """
        Initializes the RainEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use for the background.
            settings (RainSettings, optional): Configuration for the rain effect. Defaults to None.
        """
        s = validated_settings(settings, RainSettings)
        super(RainEffect, self).__init__(buffer, background, seed=s.seed)

        self.image_present = False
        self.collision = s.collision
        self.intensity = max(0, min(999, s.intensity))
        self.swells = s.swells
        self.swell_direction = 1
        self.multiplier = 1
        self.wind_direction = (
            s.wind_direction if s.wind_direction in WIND_DIRECTIONS else "none"
        )
        self.wind_mappings = {
            "east": [".\\", -1, ["\\", "."]],
            "none": [".|", 0, ["|", "."]],
            "west": ["./", 1, ["/", "."]],
        }
        self.lightning = s.lightning
        self.lightning_chance = s.lightning_chance
        self.lightning_threshold = s.lightning_threshold
        self.lightning_color = s.lightning_color
        self.lightning_color_type = s.lightning_color_type
        self._bolts = []  # list of (cells, frames_remaining)
        self._set_rain()
        self._tick = 0

    def resize(self, size: tuple[int, int]) -> None:
        """Adapt to (width, height), preserving visible rain and lightning age.

        Drops, image splashes and bolt cells keep absolute coordinates; visible
        bottom-row splashes move to the new floor. Cropped cells are discarded.
        New space starts empty and receives rain during normal updates. Explicit
        collision masks remain at their configured coordinates and dimensions.
        Intensity, wind, swell direction, tick and random streams are unchanged.
        """
        _size(size)
        width, height = size
        old_width, old_height = self.buffer.width(), self.buffer.height()
        if size == (old_width, old_height):
            super().resize(size)
            return
        columns = min(width, old_width)
        raster = Buffer(height, width).clear_buffer(val=self.background)
        for y in range(min(height, old_height)):
            raster.buffer[y][:columns] = self.buffer.buffer[y][:columns]
        if old_height:
            for x in range(columns):
                if self.buffer.get_char(x, old_height - 1) == "v":
                    raster.put_char(x, old_height - 1, self.background)
                    raster.put_char(x, height - 1, "v")
        bolts = []
        for cells, remaining in self._bolts:
            visible = [
                (x, y, char)
                for x, y, char in cells
                if 0 <= x < width and 0 <= y < height
            ]
            if visible:
                bolts.append([visible, remaining])
        self.buffer = raster
        self._bolts = bolts
        super().resize(size)

    def set_multiplier(self, val: int):
        """
        Sets the scroll multiplier (controls shift amount per simulation update).

        Args:
            val (int): Multiplier value.
        """
        self.multiplier = val

    def set_wind_direction(self, direction: str):
        """
        Sets the direction the rain falls.

        Args:
            direction (str): Wind direction ("none", "east", or "west").
        """
        if direction in WIND_DIRECTIONS:
            self.wind_direction = direction
            self._set_rain()

    def set_intensity(self, intensity: int):
        """
        Sets the intensity of the rain.

        Args:
            intensity (int): Intensity value between 0 and 999.
        """
        if self.swells:
            if self.intensity >= 900:
                self.swell_direction = -1
            if self.intensity <= 0:
                self.swell_direction = 1
            self.intensity += self.swell_direction
        else:
            self.intensity = max(0, min(999, intensity))
        self._set_rain()

    def set_swells(self, swells: bool):
        """
        Enables or disables automatic intensity oscillation.

        Args:
            swells (bool): Whether the rain intensity should oscillate.
        """
        self.swells = swells

    def set_lightning(
        self,
        lightning: bool,
        chance: float = None,
        threshold: int = None,
        color: bool = None,
        color_type: int = None,
    ):
        """
        Enables or disables lightning strikes.

        Args:
            lightning (bool): Whether to show lightning.
            chance (float, optional): Per-update probability of a new bolt (0.0–1.0).
            threshold (int, optional): Intensity threshold for lightning.
            color (bool, optional): Whether to color the lightning.
            color_type (int, optional): Color code to use for the lightning.
        """
        self.lightning = lightning
        if chance is not None:
            self.lightning_chance = chance
        if threshold is not None:
            self.lightning_threshold = threshold
        if color is not None:
            self.lightning_color = color
        if color_type is not None:
            self.lightning_color_type = color_type

    def _spawn_bolt(self):
        w = self.buffer.width()
        h = self.buffer.height()
        if w == 0 or h == 0:
            return
        bolt_height = h
        x = self.rng.randint(2, w - 3) if w >= 5 else self.rng.randint(0, w - 1)
        cells = []
        chars = ["|", "/", "\\"]
        for y in range(bolt_height):
            cells.append((x, y, self.rng.choice(chars)))
            x = max(0, min(w - 1, x + self.rng.choice([-1, 0, 0, 1])))
        self._bolts.append([cells, self.rng.randint(10, 20)])

    def _set_rain(self):
        self.rain = f"{' ' * (1000 - self.intensity)}"
        if self.intensity > 0:
            self.rain += "."
        if self.intensity > 250:
            self.rain += "."
        if self.intensity > 500:
            self.rain += self.wind_mappings[self.wind_direction][0]
        self.rain_length = len(self.rain)

    def update_collision(
        self,
        img_start_x: int,
        img_start_y: int,
        img_width: int,
        img_height: int,
        collision: bool,
        smart_transparent: bool = False,
        image_buffer: Buffer = None,
    ):
        """
        Configures collision detection with an image.

        Args:
            img_start_x (int): Image x position on screen.
            img_start_y (int): Image y position on screen.
            img_width (int): Width of the image.
            img_height (int): Height of the image.
            collision (bool): Whether to enable collision.
            smart_transparent (bool, optional): Smart transparency flag. Defaults to False.
            image_buffer (Buffer, optional): Buffer containing the image. Defaults to None.
        """
        self.image_present = (
            True if img_start_x and img_start_y and img_width and img_height else False
        )
        self.collision = collision
        if self.image_present:
            self.img_start_x = img_start_x
            self.img_start_y = img_start_y
            self.img_height = img_height
            self.img_width = img_width
            self.smart_transparent = smart_transparent
            self.image_buffer = image_buffer
        else:
            self.image_buffer = None

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        tick = self._tick
        self._tick += 1
        if self.swells:
            self.set_intensity(None)

        if self.lightning:
            for bolt, _ in self._bolts:
                for bx, by, _ in bolt:
                    self.buffer.put_char(bx, by, " ")

            self._bolts = [
                [bolt, remaining - 1]
                for bolt, remaining in self._bolts
                if remaining > 1
            ]

        if tick == 0:
            self.buffer.put_at(
                0,
                0,
                "".join(
                    self.rain[self.rng.randint(0, self.rain_length - 1)]
                    for _ in range(self.buffer.width())
                ),
            )
        else:
            self.buffer.shift(
                self.wind_mappings[self.wind_direction][1] * self.multiplier
            )
            self.buffer.scroll(-1 * self.multiplier)
            self.buffer.put_at(
                0,
                0,
                "".join(
                    self.rain[self.rng.randint(0, self.rain_length - 1)]
                    for _ in range(self.buffer.width())
                ),
            )

            if self.collision:
                for y in range(self.buffer.height()):
                    for x in range(self.buffer.width()):
                        if self.buffer.get_char(x, y) == "v":
                            self.buffer.put_char(x, y, " ")
                        else:
                            if self.image_present and self.image_buffer:
                                if 0 <= y + 1 < self.buffer.height():
                                    if (
                                        self.image_buffer.get_char(x, y + 1)
                                        not in [" ", None]
                                        and self.buffer.get_char(x, y)
                                        in self.wind_mappings[self.wind_direction][2]
                                    ):
                                        self.buffer.put_char(x, y, "v")

                            if y == self.buffer.height() - 1:
                                if (
                                    self.buffer.get_char(x, y)
                                    in self.wind_mappings[self.wind_direction][2]
                                ):
                                    self.buffer.put_char(x, y, "v")

        if self.lightning:
            if (
                self.rng.random() < self.lightning_chance
                and self.intensity >= self.lightning_threshold
            ):
                self._spawn_bolt()
            for bolt, remaining in self._bolts:
                for bx, by, ch in bolt:
                    if self.lightning_color:
                        colored_ch = bruhcolored(
                            ch, color=self.lightning_color_type
                        ).colored
                        self.buffer.put_char(bx, by, colored_ch)
                    else:
                        self.buffer.put_char(bx, by, ch)
