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
from typing import Dict, List

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil.bruhffer import Buffer
from .base_effect import BaseEffect
from .settings import FireSettings, validated_settings


class FireEffect(BaseEffect):
    """
    Class for generating a dynamic fire effect with taller, rounder,
    and more visible flames using fuller ASCII characters.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: FireSettings | None = None
    ):
        """
        Initializes the fire effect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (FireSettings, optional): Configuration for the fire effect. Defaults to None.
        """
        s = validated_settings(settings, FireSettings)
        super(FireEffect, self).__init__(buffer, background, seed=s.seed)

        self.ascii_chars = " ░▒▓██████"
        self.color_map = [232, 160, 196, 202, 208, 214, 220, 226, 231, 15]

        self.previous_data = np.zeros(
            (buffer.height(), buffer.width()), dtype=np.float32
        )
        self.current_data = np.zeros_like(self.previous_data)

        self.height_cooling_map = np.linspace(0.98, 0.92, buffer.height())[
            :, np.newaxis
        ]

        self.fire_intensity = s.intensity
        self.swell = s.swell
        self.swell_delta = 0.02
        self.swell_halt = s.swell_halt
        self.use_char_color = s.use_char_color
        self.background_color = s.background_color
        self.turbulence = max(0.0, min(1.0, s.turbulence))
        self.heat_spots: List[Dict] = []
        self.heat_spot_intensity = max(0.0, min(1.0, s.heat_spot_intensity))

        self._random_variations = self.np_rng.uniform(0.8, 1.2, (buffer.width(),))
        self._update_random_variations_counter = 0

        self.set_fire_wind(s.wind_direction, s.wind_strength)
        self._tick = 0

    def set_fire_ascii_chars(self, ascii_chars: str):
        """
        Sets the ASCII characters used for the fire effect.

        Args:
            ascii_chars (str): Exactly 10 characters to use for the fire gradient.
        """
        if len(ascii_chars) == 10:
            self.ascii_chars = ascii_chars

    def set_fire_intensity(self, fire_intensity: float):
        """
        Sets the intensity of the fire effect.

        Args:
            fire_intensity (float): Value between 0 and 1.
        """
        if 0 <= fire_intensity <= 1:
            self.fire_intensity = fire_intensity

    def set_fire_wind(self, direction: float, strength: float):
        """
        Sets wind parameters for the fire effect.

        Args:
            direction (float): Wind angle in degrees.
            strength (float): Wind strength between 0 and 1.
        """
        self.wind_direction = math.radians(direction)
        self.wind_strength = max(0.0, min(1.0, strength))

    def set_fire_use_char_color(self, use_char_color: bool):
        """
        Enables or disables character color rendering.

        Args:
            use_char_color (bool): Whether to color the ASCII characters.
        """
        self.use_char_color = use_char_color

    def set_fire_background_color(self, background_color: bool):
        """
        Enables or disables background color rendering.

        Args:
            background_color (bool): Whether to render as colored background blocks.
        """
        self.background_color = background_color

    def set_fire_swell(self, swell: bool, swell_halt: int = 1):
        """
        Controls intensity oscillation (breathing effect).

        Args:
            swell (bool): Whether to enable swelling.
            swell_halt (int, optional): Frames between swell updates. Defaults to 1.
        """
        self.swell = swell
        self.swell_halt = swell_halt

    def set_fire_turbulence(self, turbulence: float):
        """
        Sets how chaotic the fire behaves.

        Args:
            turbulence (float): Value between 0 and 1.
        """
        self.turbulence = max(0.0, min(1.0, turbulence))

    def set_fire_heat_spot_intensity(self, heat_spot_intensity: float):
        """
        Sets the intensity of heat spots.

        Args:
            heat_spot_intensity (float): Value between 0 and 1.
        """
        self.heat_spot_intensity = max(0.0, min(1.0, heat_spot_intensity))

    def get_colored_char(self, intensity: float, max_intensity: float = 255.0) -> str:
        """
        Returns a colored character based on fire intensity.

        Args:
            intensity (float): Current cell intensity.
            max_intensity (float, optional): Maximum intensity value. Defaults to 255.0.

        Returns:
            str: The character (with optional ANSI color) to render.
        """
        intensity_variation = intensity * (1 + self.rng.uniform(-0.1, 0.1))
        intensity_variation = max(0, min(intensity_variation, max_intensity))

        char_index = int(
            (intensity_variation / max_intensity) * (len(self.ascii_chars) - 1)
        )
        char_index = min(char_index, len(self.ascii_chars) - 1)

        if intensity_variation < 1:
            return " "

        if self.ascii_chars[char_index] == " ":
            return " "

        color_index = int(
            (intensity_variation / max_intensity) * (len(self.color_map) - 2)
        )
        color_index = min(color_index, len(self.color_map) - 2)

        if self.rng.random() < 0.04 and intensity > max_intensity * 0.9:
            color_index = len(self.color_map) - 1

        if self.background_color:
            return bc(text=" ", on_color=self.color_map[color_index]).colored
        elif self.use_char_color:
            return bc(
                text=self.ascii_chars[char_index], color=self.color_map[color_index]
            ).colored
        return self.ascii_chars[char_index]

    def update_data(self, frame_number: int):
        """
        Updates the fire simulation data for one frame.

        Args:
            frame_number (int): The simulation tick index, independent of draw FPS.
        """
        wind_x = (
            math.cos(self.wind_direction + math.sin(frame_number * 0.05) * 0.2)
            * self.wind_strength
        )
        wind_offset_x = int(wind_x * 2)

        left = np.roll(self.previous_data, -1, axis=1)
        right = np.roll(self.previous_data, 1, axis=1)
        up = np.roll(self.previous_data, -1, axis=0)

        base_values = (up * 1.8 + left * 1.2 + right * 1.2) / 4.2

        if wind_offset_x != 0:
            base_values = np.roll(base_values, wind_offset_x, axis=1)

        if self.turbulence > 0:
            turbulence_factor = self.np_rng.uniform(
                1 - self.turbulence, 1 + self.turbulence, base_values.shape
            )
            base_values *= turbulence_factor

        self.current_data[:-1, :] = base_values[1:, :] * self.height_cooling_map[:-1, :]

        if self.rng.random() < self.heat_spot_intensity:
            self.heat_spots.append(
                {
                    "x": self.rng.randint(0, self.buffer.width() - 1),
                    "y": self.rng.randint(
                        self.buffer.height() - 3, self.buffer.height() - 1
                    ),
                    "intensity": self.rng.uniform(0.5, 1.0),
                    "lifetime": self.rng.randint(10, 20),
                    "y_offset": 0.0,
                    "x_offset": 0.0,
                }
            )

        new_heat_spots = []
        for spot in self.heat_spots:
            if spot["lifetime"] > 0:
                spot["y_offset"] += self.rng.uniform(0, 0.5)
                spot["y"] = max(0, spot["y"] - int(spot["y_offset"]))
                spot["x_offset"] += self.rng.uniform(-0.3, 0.3)
                spot["x"] += spot["x_offset"]

                x, y = int(spot["x"]), int(spot["y"])

                if 0 <= x < self.buffer.width() and 0 <= y < self.buffer.height():
                    self.current_data[y, x] = max(
                        self.current_data[y, x], 255 * spot["intensity"]
                    )

                spot["lifetime"] -= 1
                if spot["y"] > 0:
                    new_heat_spots.append(spot)
        self.heat_spots = new_heat_spots

        self.previous_data, self.current_data = (
            self.current_data.copy(),
            self.previous_data,
        )

    def add_new_fire_row(self, frame_number: int):
        """
        Seeds a new row of heat at the bottom of the fire.

        Args:
            frame_number (int): The simulation tick index, independent of draw FPS.
        """
        if self._update_random_variations_counter % 10 == 0:
            self._random_variations = self.np_rng.uniform(
                0.8, 1.2, (self.buffer.width(),)
            )
        self._update_random_variations_counter += 1

        x_values = np.arange(self.buffer.width())
        base_intensities = self.fire_intensity * (
            1 + 0.3 * np.sin(x_values / 5 + frame_number * 0.1)
        )
        base_intensities *= self._random_variations

        random_values = self.np_rng.random(self.buffer.width())
        self.current_data[-1, :] = np.where(random_values < base_intensities, 255, 0)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        tick = self._tick
        self._tick += 1
        self.update_data(tick)

        intensities = np.clip(self.current_data, 0, 255)

        for y in range(self.buffer.height()):
            for x in range(self.buffer.width()):
                self.buffer.put_char(x, y, self.get_colored_char(intensities[y, x]))

        self.add_new_fire_row(tick)

        if self.swell and tick % self.swell_halt == 0:
            if self.fire_intensity >= 1.0:
                self.swell_delta = -0.02
            elif self.fire_intensity <= 0.1:
                self.swell_delta = 0.02
            self.fire_intensity += self.swell_delta
