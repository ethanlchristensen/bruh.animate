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

from dataclasses import dataclass, field


@dataclass
class AudioSettings:
    mode: str = "bars"
    bar_char: str = "|"
    smoothing: float = 0.7
    num_bars: int = 0
    color: bool = True
    sensitivity: float = 1.0
    compact: bool = False


@dataclass
class DrawLinesSettings:
    char: str = None
    thin: bool = False


@dataclass
class FireSettings:
    intensity: float = 0.2
    wind_direction: float = 0.0
    wind_strength: float = 0.0
    use_char_color: bool = False
    background_color: bool = False
    swell: bool = False
    swell_halt: int = 1
    turbulence: float = 0.0
    heat_spot_intensity: float = 0.1


@dataclass
class FireworkSettings:
    firework_type: str = "circular"
    color_enabled: bool = False
    color_type: str = "solid"
    rate: float = 0.05


@dataclass
class GameOfLifeSettings:
    decay: bool = False
    color: bool = False
    color_type: str = "GREYSCALE"
    scale: str = "random"


@dataclass
class MatrixSettings:
    character_halt_range: tuple = (1, 2)
    color_halt_range: tuple = (1, 2)
    character_randomness_one: float = 0.70
    character_randomness_two: float = 0.60
    color_randomness: float = 0.50
    gradient_length: int = 1


@dataclass
class NoiseSettings:
    intensity: int = 200
    color: bool = False


@dataclass
class OffsetSettings:
    direction: str = "right"


@dataclass
class PlasmaSettings:
    color: bool = False
    characters: bool = True
    random_colors: bool = False
    show_info: bool = False


@dataclass
class RainSettings:
    """Rain density on a 0-999 scale; zero disables new raindrops."""

    intensity: int = 200
    wind_direction: str = "none"
    swells: bool = False
    collision: bool = False
    lightning: bool = False
    lightning_chance: float = 0.02
    lightning_threshold: int = 500
    lightning_color: bool = False
    lightning_color_type: int = 226


@dataclass
class SnowSettings:
    intensity: float = 0.01
    wind: float = 0.0
    show_info: bool = False
    collision: bool = False


@dataclass
class StarSettings:
    color_type: str = "GREYSCALE"


@dataclass
class TwinkleSettings:
    twinkle_chars: list = field(default_factory=lambda: ["."])
    density: float = 0.05


@dataclass
class BoidsSettings:
    num_boids: int = 60
    color: bool = True
    char: str = "*"
    max_speed: float = 1.5
    perception: float = 12.0


@dataclass
class SandSettings:
    color: bool = True
    char: str = "#"
    spawn_rate: float = 0.2


@dataclass
class DiffusionSettings:
    color: bool = True
    char: str = "."
    f: float = 0.055
    k: float = 0.062
    steps_per_frame: int = 8


@dataclass
class AutomatonSettings:
    color: bool = True
    char: str = "#"
    rule: int = 30


@dataclass
class VoronoiSettings:
    color: bool = True
    char: str = "#"
    num_seeds: int = 12
    seed_speed: float = 0.3


@dataclass
class PerlinSettings:
    color: bool = True
    char: str = "."
    octaves: int = 4
    speed: float = 0.015
    threshold: float = 0.35
