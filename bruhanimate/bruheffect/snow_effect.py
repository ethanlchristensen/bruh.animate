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

from ..bruhutil import FLAKE_WEIGHT_CHARS, SNOWFLAKE_COLORS, SNOWFLAKE_TYPES, Buffer
from ..resize import _size
from .base_effect import BaseEffect
from .settings import SnowSettings, validated_settings


class SnowEffect(BaseEffect):
    """
    A class to represent a snow effect.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: SnowSettings | None = None
    ):
        """
        Initializes the SnowEffect.

        Args:
            buffer (Buffer): Effect buffer to render changes to.
            background (str): Character or string used for the background of the effect.
            settings (SnowSettings, optional): Configuration for the snow effect. Defaults to None.
        """
        s = validated_settings(settings, SnowSettings)
        super(SnowEffect, self).__init__(buffer, background, seed=s.seed)

        self.image_present = False
        self.collision = s.collision
        self.show_info = s.show_info
        self.snow_intensity = max(0.0, min(1.0, s.intensity))
        self.wind = max(-1.0, min(1.0, s.wind))

        self.flakes = []
        self.ground_flakes = [
            [0 for _ in range(buffer.width())] for _ in range(buffer.height())
        ]
        self.image_flakes = [None for _ in range(self.buffer.width())]
        self.smart_transparent = False
        self.total_ground_flakes = 0

    def resize(self, size: tuple[int, int]) -> None:
        """Adapt the simulation to (width, height) without advancing a tick.

        Floor-connected piles keep their depth relative to the bottom and their
        column. Other settled snow and explicit collision surfaces keep absolute
        coordinates. Falling flakes keep position, drift and delay when visible.
        Cropped snow, and flakes covered by a relocated pile, are discarded;
        growing later does not restore them. Newly exposed columns start empty.
        Random streams, settings and lifecycle are unchanged. The new raster is
        painted immediately, including before the next scheduled update.
        """
        _size(size)
        width, height = size
        old_width, old_height = self.buffer.width(), self.buffer.height()
        if size == (old_width, old_height):
            super().resize(size)
            return

        ground = [[0] * width for _ in range(height)]
        for x in range(min(width, old_width)):
            # Only the contiguous stack resting on the floor follows the floor.
            # Snow on a configured image must not move along with that stack.
            floor_top = old_height
            while floor_top > 0 and self.ground_flakes[floor_top - 1][x] > 0:
                floor_top -= 1
            for y in range(old_height):
                target_y = y + height - old_height if y >= floor_top else y
                if 0 <= target_y < height:
                    ground[target_y][x] += self.ground_flakes[y][x]

        flakes = [
            flake
            for flake in self.flakes
            if 0 <= flake["x"] < width
            and 0 <= flake["y"] < height
            and ground[flake["y"]][flake["x"]] == 0
        ]
        raster = Buffer(height, width).clear_buffer(val=self.background)
        weights = sorted(FLAKE_WEIGHT_CHARS.items(), reverse=True)
        for y, row in enumerate(ground):
            for x, count in enumerate(row):
                for weight, character in weights:
                    if count >= weight:
                        raster.put_char(x, y, character)
                        break
        for flake in flakes:
            raster.put_char(flake["x"], flake["y"], flake["colored"].colored)

        self.buffer = raster
        self.ground_flakes = ground
        self.flakes = flakes
        self.image_flakes = self.image_flakes[:width] + [None] * max(
            0, width - old_width
        )
        if self.show_info:
            self.add_info()
        super().resize(size)

    def set_snow_intensity(self, intensity: float):
        """
        Sets the probability of a new snowflake spawning per column per simulation update.

        Args:
            intensity (float): Value between 0.0 and 1.0. Zero disables new flakes.
        """
        if 0.0 <= intensity <= 1.0:
            self.snow_intensity = intensity

    def set_wind(self, wind: float):
        """
        Sets the horizontal wind bias that influences snowflake drift.

        Args:
            wind (float): Wind strength from -1.0 (hard left) to 1.0 (hard right).
        """
        self.wind = max(-1.0, min(1.0, wind))

    def set_show_info(self, show_info: bool):
        """
        Toggles the snowflake debug info overlay.

        Args:
            show_info (bool): Whether to show flake counts on screen.
        """
        self.show_info = show_info

    def update_collision(
        self,
        img_start_x: int,
        img_start_y: int,
        img_width: int,
        img_height: int,
        collision: bool,
        smart_transparent: bool,
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
            smart_transparent (bool): Smart transparency flag.
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
            self.img_end_y = img_start_y + img_height
            self.image_buffer = image_buffer
            self.image_x_boundaries = (img_start_x, img_start_x + img_width)
            self.image_y_boundaries = (img_start_y, img_start_y + img_height)
        else:
            self.image_buffer = None

    def generate_snowflake(self, x: int):
        """
        Generates a new snowflake at the given x position with a wind-influenced drift bias.

        Args:
            x (int): The x position to spawn the snowflake at.
        """
        snowflake_type = self.rng.choice(list(SNOWFLAKE_TYPES.keys()))
        snowflake_char = bruhcolored(snowflake_type, SNOWFLAKE_COLORS[snowflake_type])
        drift_bias = self.wind + self.rng.uniform(-0.35, 0.35)
        self.flakes.append(
            {
                "x": x,
                "y": 0,
                "type": snowflake_type,
                "colored": snowflake_char,
                "fall_delay": 0,
                "drift_bias": drift_bias,
            }
        )

    def can_stack(self, x: int, y: int) -> bool:
        """
        Checks whether accumulated snow at (x, y) is dense enough to stack onto the row above.

        Args:
            x (int): Column to check.
            y (int): Row to check.

        Returns:
            bool: True if snow should stack upward.
        """
        if y >= self.buffer.height():
            return False
        return self.ground_flakes[y][x] >= 18

    def is_colliding(self, x: int, y: int) -> bool:
        """
        Checks whether a snowflake at (x, y) would collide with an image.

        Args:
            x (int): Column to check.
            y (int): Row to check.

        Returns:
            bool: True if the position is inside the image boundary.
        """
        if self.image_present:
            if (
                self.image_x_boundaries[0] < x < self.image_x_boundaries[1]
                and self.image_y_boundaries[0] < y < self.image_y_boundaries[1]
            ):
                return True
        return False

    def handle_snowflake_landing(self, x: int, y: int):
        """
        Accumulates snow at the landing position and updates the ground character.

        Args:
            x (int): Column where the flake landed.
            y (int): Row where the flake landed.
        """
        self.ground_flakes[y][x] += 1
        weight = self.ground_flakes[y][x]
        for w, char in sorted(FLAKE_WEIGHT_CHARS.items(), reverse=True):
            if weight >= w:
                self.buffer.put_char(x, y, char)
                break
        if weight > 18 and y > 0:
            self.ground_flakes[y - 1][x] += 1

    def add_info(self):
        """
        Renders debug info (flake counts) at the top of the buffer.
        """
        self.buffer.put_at(0, 0, f"Total Snow Flakes: {len(self.flakes)}")
        self.buffer.put_at(
            0,
            1,
            f"Total Flakes on Ground: {sum(1 for row in self.ground_flakes for v in row if v > 0)}",
        )

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        for idx in range(self.buffer.width()):
            if self.rng.random() < self.snow_intensity:
                self.generate_snowflake(idx)

        new_flakes = []
        for snowflake in self.flakes:
            x, y, flake_type = snowflake["x"], snowflake["y"], snowflake["type"]
            speed = SNOWFLAKE_TYPES[flake_type]["speed"]

            self.buffer.put_char(x, y, " ")

            if snowflake["fall_delay"] < speed:
                snowflake["fall_delay"] += 1
                new_flakes.append(snowflake)
                continue
            else:
                snowflake["fall_delay"] = 0

            if y + 1 >= self.buffer.height() or self.can_stack(x, y + 1):
                self.handle_snowflake_landing(x, y)
            else:
                snowflake["drift_bias"] = max(
                    -2.0,
                    min(2.0, snowflake["drift_bias"] + self.rng.uniform(-0.08, 0.08)),
                )
                bias = snowflake["drift_bias"]
                left_w = max(0.05, 1.0 - bias)
                right_w = max(0.05, 1.0 + bias)
                dx = self.rng.choices([-1, 0, 1], weights=[left_w, 1.2, right_w])[0]

                new_x = max(0, min(self.buffer.width() - 1, x + dx))
                new_y = y + 1
                if (
                    new_y < self.buffer.height()
                    and not self.is_colliding(new_x, new_y)
                    and 0 <= new_x < self.buffer.width()
                ):
                    snowflake["x"], snowflake["y"] = new_x, new_y
                    new_flakes.append(snowflake)
                else:
                    self.handle_snowflake_landing(x, y)

        self.flakes = new_flakes

        for snowflake in self.flakes:
            self.buffer.put_char(
                snowflake["x"], snowflake["y"], snowflake["colored"].colored
            )

        if self.show_info:
            self.add_info()
