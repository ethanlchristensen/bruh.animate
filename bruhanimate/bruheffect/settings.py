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
import types
import unicodedata
from dataclasses import dataclass, field, fields
from typing import Literal, TypeVar, get_args, get_origin, get_type_hints

from ..bruhutil.bruhtypes import FireworkColorType, FireworkType

AudioMode = Literal[
    "bars",
    "mirror",
    "waveform",
    "spectrum",
    "radial",
    "rain",
    "tunnel",
    "ripple",
    "vortex",
    "wave",
    "starfield",
    "fireworks",
    "interference",
    "bounce",
    "lightning",
    "aurora",
    "orbit",
    "orbit_gradient",
    "scope",
    "grid",
    "helix",
    "lissajous",
    "sunburst",
    "mandala",
    "comet",
    "weave",
]
LifePalette = Literal[
    "GREYSCALE", "GREYSCALE_r", "GREYSCALE_MUTED", "RAINBOW", "RAINBOW_r"
]
LifeScale = Literal["random", "default", ".", "o", "0"]
OffsetDirection = Literal["left", "right"]
WindDirection = Literal["none", "east", "west"]

T = TypeVar("T")


def _bounded(default: T, low: float, high: float | None = None, *, help: str = "") -> T:
    return field(default=default, metadata={"min": low, "max": high, "help": help})


def _glyph(value: str, name: str) -> None:
    if (
        len(value) != 1
        or unicodedata.category(value).startswith(("C", "M"))
        or unicodedata.east_asian_width(value) in ("W", "F")
    ):
        raise ValueError(f"{name} must be one printable single-cell character")


def _check_type(value: object, annotation: object, name: str) -> None:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if value not in args:
            raise ValueError(f"{name} must be one of {', '.join(map(repr, args))}")
    elif origin is types.UnionType:
        if value is None and type(None) in args:
            return
        _check_type(value, next(arg for arg in args if arg is not type(None)), name)
    elif origin in (tuple, list):
        if not isinstance(value, origin):
            raise TypeError(f"{name} must be a {origin.__name__}")
        if origin is tuple and len(value) != len(args):
            raise ValueError(f"{name} must contain {len(args)} values")
        for index, item in enumerate(value):
            _check_type(
                item, args[0] if origin is list else args[index], f"{name}[{index}]"
            )
    elif annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    elif annotation in (int, bool, str):
        if type(value) is not annotation:
            raise TypeError(f"{name} must be {annotation.__name__}")


@dataclass
class EffectSettings:
    """Validated built-in configuration, with typed fields and explicit ranges.

    Construction rejects wrong types (TypeError) and invalid values (ValueError).
    Effects revalidate supplied settings before use, including edited instances.
    Settings remain mutable; editing one does not reconfigure an existing effect.
    Probabilities and halt ranges use simulation ticks, not display frames.
    seed selects independent Python/NumPy streams; None uses fresh entropy.
    Equal seeds reproduce a fresh effect with equal settings, size and updates
    in the same dependency versions. External inputs (such as audio) must match.
    """

    seed: int | None = field(
        default=None,
        kw_only=True,
        metadata={"min": 0, "help": "Independent random seed; None uses fresh entropy"},
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate every field without clamping or changing the configuration."""
        hints = get_type_hints(type(self))
        for item in fields(self):
            value = getattr(self, item.name)
            name = f"{type(self).__name__}.{item.name}"
            _check_type(value, hints[item.name], name)
            if value is None:
                continue
            low, high = item.metadata.get("min"), item.metadata.get("max")
            if low is not None and value < low:
                raise ValueError(f"{name} must be at least {low}")
            if high is not None and value > high:
                raise ValueError(f"{name} must be at most {high}")
            if item.name in ("char", "bar_char") and value is not None:
                _glyph(value, name)
            if item.name.endswith("_halt_range"):
                if not 1 <= value[0] <= value[1]:
                    raise ValueError(
                        f"{name} must be an ordered pair of positive tick counts"
                    )
            if item.name == "twinkle_chars":
                if not value:
                    raise ValueError(f"{name} must not be empty")
                for glyph in value:
                    _glyph(glyph, name)


S = TypeVar("S", bound=EffectSettings)


def validated_settings(value: S | None, expected: type[S]) -> S:
    """Get defaults or validate a supplied configuration before effect allocation."""
    if value is None:
        return expected()
    if not isinstance(value, expected):
        raise TypeError(
            f"settings must be {expected.__name__}, got {type(value).__name__}"
        )
    value.validate()
    return value


@dataclass
class AudioSettings(EffectSettings):
    """Audio display. num_bars=0 selects automatically; smoothing is in [0, 1]."""

    mode: AudioMode = "bars"
    bar_char: str = "|"
    smoothing: float = _bounded(0.7, 0, 1)
    num_bars: int = _bounded(0, 0, help="0 selects a bar count from terminal width")
    color: bool = True
    sensitivity: float = _bounded(1.0, 0)
    compact: bool = False


@dataclass
class DrawLinesSettings(EffectSettings):
    """Single-cell line glyph; None chooses the built-in line characters."""

    char: str | None = None
    thin: bool = False


@dataclass
class FireSettings(EffectSettings):
    """Fire probabilities/strengths in [0, 1]; wind_direction is degrees."""

    intensity: float = _bounded(0.2, 0, 1)
    wind_direction: float = 0.0
    wind_strength: float = _bounded(0.0, 0, 1)
    use_char_color: bool = False
    background_color: bool = False
    swell: bool = False
    swell_halt: int = _bounded(1, 1, help="Simulation ticks between swell updates")
    turbulence: float = _bounded(0.0, 0, 1)
    heat_spot_intensity: float = _bounded(0.1, 0, 1)


@dataclass
class FireworkSettings(EffectSettings):
    """Burst style and per-tick launch probability; rate=0 disables launches."""

    firework_type: FireworkType = "circular"
    color_enabled: bool = False
    color_type: FireworkColorType = "solid"
    rate: float = _bounded(0.05, 0, 1)


@dataclass
class GameOfLifeSettings(EffectSettings):
    """Life display palette and optional decay glyph scale."""

    decay: bool = False
    color: bool = False
    color_type: LifePalette = "GREYSCALE"
    scale: LifeScale = "random"


@dataclass
class MatrixSettings(EffectSettings):
    """Positive ordered tick ranges and probabilities in [0, 1]."""

    character_halt_range: tuple[int, int] = (1, 2)
    color_halt_range: tuple[int, int] = (1, 2)
    character_randomness_one: float = _bounded(0.70, 0, 1)
    character_randomness_two: float = _bounded(0.60, 0, 1)
    color_randomness: float = _bounded(0.50, 0, 1)
    gradient_length: int = _bounded(1, 1)


@dataclass
class NoiseSettings(EffectSettings):
    """Noise density on a 0-999 scale; zero disables new noise."""

    intensity: int = _bounded(200, 0, 999)
    color: bool = False


@dataclass
class OffsetSettings(EffectSettings):
    """Supported horizontal offset pattern directions."""

    direction: OffsetDirection = "right"


@dataclass
class PlasmaSettings(EffectSettings):
    """Plasma glyph and palette rendering switches."""

    color: bool = False
    characters: bool = True
    random_colors: bool = False
    show_info: bool = False


@dataclass
class RainSettings(EffectSettings):
    """Density in [0, 999], lightning probability in [0, 1], color in [0, 255]."""

    intensity: int = _bounded(200, 0, 999, help="0 disables new raindrops")
    wind_direction: WindDirection = "none"
    swells: bool = False
    collision: bool = False
    lightning: bool = False
    lightning_chance: float = _bounded(0.02, 0, 1)
    lightning_threshold: int = _bounded(500, 0, 999)
    lightning_color: bool = False
    lightning_color_type: int = _bounded(
        226, 0, 255, help="ANSI palette index; 0 is black"
    )


@dataclass
class SnowSettings(EffectSettings):
    """Per-tick flake probability in [0, 1]; wind in [-1, 1] (left to right)."""

    intensity: float = _bounded(
        0.01, 0, 1, help="Per-column flake probability per tick; 0 disables new flakes"
    )
    wind: float = _bounded(0.0, -1, 1, help="-1 blows left, 0 is calm, 1 blows right")
    show_info: bool = False
    collision: bool = False


@dataclass
class StarSettings(EffectSettings):
    """Palette for the blinking star field."""

    color_type: LifePalette = "GREYSCALE"


@dataclass
class TwinkleSettings(EffectSettings):
    """Nonempty single-cell glyph list and fraction of twinkling cells in [0, 1]."""

    twinkle_chars: list[str] = field(default_factory=lambda: ["."])
    density: float = _bounded(0.05, 0, 1)


@dataclass
class BoidsSettings(EffectSettings):
    """Flock count, single-cell glyph, speed per tick and perception radius."""

    num_boids: int = _bounded(60, 0)
    color: bool = True
    char: str = "*"
    max_speed: float = _bounded(
        1.5, 0.3, help="Cells per tick; minimum cruise speed is 0.3"
    )
    perception: float = _bounded(12.0, 0)


@dataclass
class SandSettings(EffectSettings):
    """Single-cell sand glyph and per-tick spawn probability in [0, 1]."""

    color: bool = True
    char: str = "#"
    spawn_rate: float = _bounded(0.2, 0, 1)


@dataclass
class DiffusionSettings(EffectSettings):
    """Feed/kill rates in [0, 1]; steps_per_frame counts substeps per update tick."""

    color: bool = True
    char: str = "."
    f: float = _bounded(0.055, 0, 1)
    k: float = _bounded(0.062, 0, 1)
    steps_per_frame: int = _bounded(
        8, 1, help="Numerical substeps per simulation tick (historical field name)"
    )


@dataclass
class AutomatonSettings(EffectSettings):
    """Elementary cellular automaton rule number in [0, 255]."""

    color: bool = True
    char: str = "#"
    rule: int = _bounded(30, 0, 255)


@dataclass
class VoronoiSettings(EffectSettings):
    """Positive seed count and non-negative seed speed per tick."""

    color: bool = True
    char: str = "#"
    num_seeds: int = _bounded(12, 1)
    seed_speed: float = _bounded(0.3, 0)


@dataclass
class PerlinSettings(EffectSettings):
    """Positive octave count, non-negative speed per tick, threshold in [0, 1]."""

    color: bool = True
    char: str = "."
    octaves: int = _bounded(4, 1)
    speed: float = _bounded(0.015, 0)
    threshold: float = _bounded(0.35, 0, 1)
