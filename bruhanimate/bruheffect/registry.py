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

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Type

from .settings import EffectSettings

if TYPE_CHECKING:
    from ..bruhutil.bruhffer import Buffer
    from .base_effect import BaseEffect


@dataclass
class EffectEntry:
    """Metadata for a single registered effect."""

    name: str
    effect_cls: Type
    settings_cls: Type | None
    description: str
    presets: dict[str, Any] = field(default_factory=dict)


class EffectRegistry:
    """
    Central registry that maps effect names to their implementation class,
    settings class, description, and named presets.

    Usage::

        from bruhanimate import effect_registry

        # list all registered effects
        for name, entry in effect_registry.entries().items():
            print(name, "—", entry.description)

        # create an effect by name (returns a BaseEffect instance)
        effect = effect_registry.create("snow", buffer, " ")

        # create with a named preset
        effect = effect_registry.create("snow", buffer, " ", preset="blizzard")

        # create with a custom settings object
        from bruhanimate import SnowSettings
        effect = effect_registry.create("snow", buffer, " ", settings=SnowSettings(wind=0.8))

        # register your own effect
        effect_registry.register(
            "myeffect",
            MyEffect,
            settings_cls=MySettings,
            description="Does something cool",
            presets={"fast": MySettings(speed=10)},
        )
    """

    def __init__(self):
        self._registry: dict[str, EffectEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        effect_cls: Type,
        settings_cls: Type | None = None,
        description: str = "",
        presets: dict[str, Any] | None = None,
    ) -> None:
        """Register an effect, validating and copying its preset configurations.

        Custom settings classes need not inherit EffectSettings. Their instances
        are type-checked; built-in EffectSettings also validate field values.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("An effect name must be a nonempty string")
        if settings_cls is not None and not isinstance(settings_cls, type):
            raise TypeError("settings_cls must be a class or None")
        for preset_name, configuration in (presets or {}).items():
            if not isinstance(preset_name, str) or not preset_name.strip():
                raise ValueError("A preset name must be a nonempty string")
            self._validate_settings(name, settings_cls, configuration)
        self._registry[name] = EffectEntry(
            name=name,
            effect_cls=effect_cls,
            settings_cls=settings_cls,
            description=description,
            presets=deepcopy(presets or {}),
        )

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get(self, name: str) -> EffectEntry:
        """Return the :class:`EffectEntry` for *name*, or raise ``KeyError``."""
        if name not in self._registry:
            raise KeyError(
                f"'{name}' is not registered. "
                f"Available effects: {sorted(self._registry)}"
            )
        return self._registry[name]

    def names(self) -> list[str]:
        """Return a sorted list of all registered effect names."""
        return sorted(self._registry)

    def entries(self) -> dict[str, EffectEntry]:
        """Return a copy of the full registry dict."""
        return dict(self._registry)

    def presets(self, name: str) -> dict[str, Any]:
        """Return independent settings copies keyed by preset name.

        For example, presets('snow')['light'] is SnowSettings(intensity=0.005,
        wind=0.0, show_info=False, collision=False). Editing it is safe.
        """
        return deepcopy(self.get(name).presets)

    @staticmethod
    def _validate_settings(name: str, expected: type | None, settings: object) -> None:
        if expected is None:
            raise TypeError(f"Effect '{name}' does not accept settings")
        if not isinstance(settings, expected):
            raise TypeError(
                f"Effect '{name}' requires {expected.__name__}, "
                f"got {type(settings).__name__}"
            )
        if isinstance(settings, EffectSettings):
            settings.validate()

    def resolve_settings(
        self,
        name: str,
        *,
        settings: object | None = None,
        preset: str | None = None,
        seed: int | None = None,
    ) -> object | None:
        """Validate a selection without constructing an effect or opening resources.

        Explicit settings override a known preset. Unknown presets always raise
        KeyError with available names. Preset values are copied before use.
        None leaves the effect constructor responsible for its defaults.
        A supplied seed overrides the selected EffectSettings on an independent
        copy. None preserves the seed in the selected settings or preset.
        """
        entry = self.get(name)
        if preset is not None and preset not in entry.presets:
            raise KeyError(
                f"Preset '{preset}' not found for '{name}'. "
                f"Available: {sorted(entry.presets)}"
            )
        if settings is None and preset is not None:
            settings = deepcopy(entry.presets[preset])
        if settings is not None:
            self._validate_settings(name, entry.settings_cls, settings)
        if seed is not None:
            if entry.settings_cls is None or not issubclass(
                entry.settings_cls, EffectSettings
            ):
                raise TypeError(f"Effect '{name}' does not accept a seed override")
            selected = settings if settings is not None else entry.settings_cls()
            assert isinstance(selected, EffectSettings)
            settings = replace(deepcopy(selected), seed=seed)
        return settings

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __repr__(self) -> str:
        names = ", ".join(sorted(self._registry))
        return f"EffectRegistry([{names}])"

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        buffer: "Buffer",
        background: str,
        *,
        settings: object | None = None,
        preset: str | None = None,
        seed: int | None = None,
    ) -> "BaseEffect":
        """
        Instantiate the named effect.

        Priority: *settings* > *preset* > effect defaults.

        Args:
            name:       Registered effect name (e.g. ``"snow"``).
            buffer:     The :class:`Buffer` the effect will draw into.
            background: Background fill character.
            settings:   A settings dataclass instance to pass directly.
            preset:     Name of a registered preset to use when *settings*
                        is not provided.

        Returns:
            A ready-to-use ``BaseEffect`` instance.
        """
        entry = self.get(name)
        settings = self.resolve_settings(
            name, settings=settings, preset=preset, seed=seed
        )
        if not isinstance(background, str):
            raise TypeError("background must be a string")
        if not background:
            raise ValueError("background must not be empty")
        if settings is not None:
            return entry.effect_cls(buffer, background, settings=settings)
        return entry.effect_cls(buffer, background)


# ---------------------------------------------------------------------------
# Module-level singleton — populated below
# ---------------------------------------------------------------------------

effect_registry = EffectRegistry()


# Deferred imports to avoid circular deps (registry.py is imported by __init__)
def _populate():
    from .audio_effect import AudioEffect
    from .automaton_effect import AutomatonEffect
    from .boids_effect import BoidsEffect
    from .cloth_effect import ClothEffect
    from .diffusion_effect import DiffusionEffect
    from .draw_lines_effect import DrawLinesEffect
    from .fire_effect import FireEffect
    from .firework_effect import FireworkEffect
    from .game_of_life_effect import GameOfLifeEffect
    from .julia_effect import JuliaEffect
    from .matrix_effect import MatrixEffect
    from .metaballs_effect import MetaballsEffect
    from .noise_effect import NoiseEffect
    from .offset_effect import OffsetEffect
    from .perlin_effect import PerlinEffect
    from .plasma_effect import PlasmaEffect
    from .rain_effect import RainEffect
    from .sand_effect import SandEffect
    from .settings import (
        AudioSettings,
        AutomatonSettings,
        BoidsSettings,
        ClothSettings,
        DiffusionSettings,
        DrawLinesSettings,
        FireSettings,
        FireworkSettings,
        GameOfLifeSettings,
        MatrixSettings,
        MetaballsSettings,
        NoiseSettings,
        OffsetSettings,
        PerlinSettings,
        PlasmaSettings,
        RainSettings,
        SandSettings,
        SmokeSettings,
        SnowSettings,
        StarSettings,
        TerrainSettings,
        TwinkleSettings,
        VoronoiSettings,
        WaterSettings,
    )
    from .smoke_effect import SmokeEffect
    from .snow_effect import SnowEffect
    from .star_effect import StarEffect
    from .static_effect import StaticEffect
    from .terrain_effect import TerrainEffect
    from .twinkle_effect import TwinkleEffect
    from .voronoi_effect import VoronoiEffect
    from .water_effect import WaterEffect

    effect_registry.register(
        "static",
        StaticEffect,
        settings_cls=None,
        description="Fills the screen with a static background character.",
    )
    effect_registry.register(
        "offset",
        OffsetEffect,
        settings_cls=OffsetSettings,
        description="Scrolling offset background.",
        presets={
            "right": OffsetSettings(direction="right"),
            "left": OffsetSettings(direction="left"),
        },
    )
    effect_registry.register(
        "noise",
        NoiseEffect,
        settings_cls=NoiseSettings,
        description="Random noise pixels.",
        presets={
            "sparse": NoiseSettings(intensity=50, color=False),
            "dense": NoiseSettings(intensity=200, color=False),
            "color": NoiseSettings(intensity=150, color=True),
        },
    )
    effect_registry.register(
        "stars",
        StarEffect,
        settings_cls=StarSettings,
        description="Blinking star field.",
        presets={
            "greyscale": StarSettings(color_type="GREYSCALE"),
            "color": StarSettings(color_type="RAINBOW"),
        },
    )
    effect_registry.register(
        "plasma",
        PlasmaEffect,
        settings_cls=PlasmaSettings,
        description="Animated sine-wave plasma.",
        presets={
            "greyscale": PlasmaSettings(color=False),
            "color": PlasmaSettings(color=True, characters=True),
            "blocks": PlasmaSettings(color=True, characters=False),
            "random": PlasmaSettings(color=True, random_colors=True),
        },
    )
    effect_registry.register(
        "gol",
        GameOfLifeEffect,
        settings_cls=GameOfLifeSettings,
        description="Conway's Game of Life with optional color decay.",
        presets={
            "plain": GameOfLifeSettings(decay=False, color=False),
            "decay": GameOfLifeSettings(decay=True, color=False),
            "color": GameOfLifeSettings(decay=True, color=True, color_type="RAINBOW"),
        },
    )
    effect_registry.register(
        "rain",
        RainEffect,
        settings_cls=RainSettings,
        description="Falling rain with wind direction and collision.",
        presets={
            "drizzle": RainSettings(intensity=100, wind_direction="none"),
            "storm": RainSettings(intensity=600, wind_direction="east", swells=True),
            "thunderstorm": RainSettings(
                intensity=700,
                wind_direction="east",
                swells=True,
                lightning=True,
                lightning_chance=0.03,
            ),
            "monsoon": RainSettings(
                intensity=900,
                wind_direction="east",
                swells=True,
                collision=True,
                lightning=True,
                lightning_chance=0.05,
            ),
        },
    )
    effect_registry.register(
        "matrix",
        MatrixEffect,
        settings_cls=MatrixSettings,
        description="Cascading random-character digital rain.",
        presets={
            "default": MatrixSettings(),
            "fast": MatrixSettings(
                character_halt_range=(1, 1), color_halt_range=(1, 1), gradient_length=3
            ),
        },
    )
    effect_registry.register(
        "drawlines",
        DrawLinesEffect,
        settings_cls=DrawLinesSettings,
        description="Bresenham line drawing onto the buffer.",
        presets={
            "thin": DrawLinesSettings(thin=True),
            "thick": DrawLinesSettings(thin=False),
        },
    )
    effect_registry.register(
        "snow",
        SnowEffect,
        settings_cls=SnowSettings,
        description="Falling snow with wind and ground accumulation.",
        presets={
            "light": SnowSettings(intensity=0.005, wind=0.0),
            "moderate": SnowSettings(intensity=0.015, wind=0.2),
            "blizzard": SnowSettings(intensity=0.04, wind=0.7),
            "windy": SnowSettings(intensity=0.01, wind=0.9),
        },
    )
    effect_registry.register(
        "twinkle",
        TwinkleEffect,
        settings_cls=TwinkleSettings,
        description="Characters that pulse in brightness.",
        presets={
            "sparse": TwinkleSettings(density=0.02),
            "dense": TwinkleSettings(density=0.15),
        },
    )
    effect_registry.register(
        "firework",
        FireworkEffect,
        settings_cls=FireworkSettings,
        description="Firework explosions with multiple burst patterns.",
        presets={
            "plain": FireworkSettings(color_enabled=False),
            "color": FireworkSettings(color_enabled=True, color_type="rainbow"),
            "random": FireworkSettings(
                firework_type="random", color_enabled=True, color_type="random"
            ),
        },
    )
    effect_registry.register(
        "fire",
        FireEffect,
        settings_cls=FireSettings,
        description="Particle-based fire simulation.",
        presets={
            "campfire": FireSettings(intensity=0.15, turbulence=0.05),
            "inferno": FireSettings(intensity=0.5, turbulence=0.2, swell=True),
            "windy": FireSettings(
                intensity=0.3, wind_direction=90.0, wind_strength=0.6
            ),
        },
    )
    effect_registry.register(
        "julia",
        JuliaEffect,
        settings_cls=None,
        description="Animated Julia-set fractal.",
    )

    effect_registry.register(
        "boids",
        BoidsEffect,
        settings_cls=BoidsSettings,
        description="Reynolds flocking simulation: separation, alignment, and cohesion rules.",
        presets={
            "default": BoidsSettings(),
            "dense": BoidsSettings(num_boids=120),
            "fast": BoidsSettings(num_boids=60, max_speed=3.0),
        },
    )
    effect_registry.register(
        "sand",
        SandEffect,
        settings_cls=SandSettings,
        description="Falling-sand cellular automaton; particles spawn at the top and pile up.",
        presets={
            "light": SandSettings(spawn_rate=0.05),
            "normal": SandSettings(spawn_rate=0.20),
            "heavy": SandSettings(spawn_rate=0.50),
        },
    )
    effect_registry.register(
        "diffusion",
        DiffusionEffect,
        settings_cls=DiffusionSettings,
        description="Gray-Scott reaction-diffusion; produces evolving organic spots and stripes.",
        presets={
            "coral": DiffusionSettings(f=0.0545, k=0.062),
            "spots": DiffusionSettings(f=0.035, k=0.065),
            "stripes": DiffusionSettings(f=0.026, k=0.051),
            "organic": DiffusionSettings(shading=True, seed_pattern="scattered"),
        },
    )
    effect_registry.register(
        "automaton",
        AutomatonEffect,
        settings_cls=AutomatonSettings,
        description="Wolfram 1-D elementary cellular automaton scrolling downward.",
        presets={
            "rule30": AutomatonSettings(rule=30),
            "rule90": AutomatonSettings(rule=90),
            "rule110": AutomatonSettings(rule=110),
            "rule184": AutomatonSettings(rule=184),
        },
    )
    effect_registry.register(
        "voronoi",
        VoronoiEffect,
        settings_cls=VoronoiSettings,
        description="Animated Voronoi diagram with drifting seed points.",
        presets={
            "slow": VoronoiSettings(seed_speed=0.1),
            "fast": VoronoiSettings(seed_speed=0.8),
            "dense": VoronoiSettings(num_seeds=24, seed_speed=0.3),
        },
    )
    effect_registry.register(
        "perlin",
        PerlinEffect,
        settings_cls=PerlinSettings,
        description="Smooth animated noise field built from multiple sine-wave octaves.",
        presets={
            "sparse": PerlinSettings(threshold=0.55),
            "dense": PerlinSettings(threshold=0.20),
            "fast": PerlinSettings(speed=0.05),
        },
    )
    effect_registry.register(
        "audio",
        AudioEffect,
        settings_cls=AudioSettings,
        description="Audio-reactive objects, frequency tiles, moving light pools, EQ bars and volume/frequency history.",
        presets={
            "objects": AudioSettings(mode="objects", smoothing=0.65),
            "tiles": AudioSettings(mode="tiles", smoothing=0.75),
            "glow": AudioSettings(mode="glow", smoothing=0.8),
            "bars": AudioSettings(mode="bars", color=True, bar_char="#", smoothing=0.7),
            "mirror": AudioSettings(
                mode="mirror", color=True, bar_char="#", smoothing=0.7
            ),
            "waveform": AudioSettings(mode="waveform", color=True, smoothing=0.6),
            "spectrum": AudioSettings(mode="spectrum", color=True, smoothing=0.6),
            "minimal": AudioSettings(mode="bars", color=False, smoothing=0.6),
        },
    )

    effect_registry.register(
        "water",
        WaterEffect,
        settings_cls=WaterSettings,
        description="Damped water ripples with reflecting edges and interacting impulses.",
        presets={
            "pond": WaterSettings(),
            "rain": WaterSettings(drop_chance=0.5, damping=0.975),
            "storm": WaterSettings(drop_chance=0.9, strength=2.0, damping=0.97),
        },
    )
    effect_registry.register(
        "smoke",
        SmokeEffect,
        settings_cls=SmokeSettings,
        description="Rising smoke or sinking ink, with density advection and obstacles.",
        presets={
            "plume": SmokeSettings(),
            "ink": SmokeSettings(style="ink", turbulence=0.8, decay=0.995),
            "windy": SmokeSettings(turbulence=0.9, source_width=0.25),
        },
    )
    effect_registry.register(
        "metaballs",
        MetaballsEffect,
        settings_cls=MetaballsSettings,
        description="Implicit blobs merging and separating along independent orbits.",
        presets={
            "lava": MetaballsSettings(),
            "orbit": MetaballsSettings(count=3, speed=0.06, radius=0.22),
            "outline": MetaballsSettings(filled=False),
        },
    )
    effect_registry.register(
        "cloth",
        ClothEffect,
        settings_cls=ClothSettings,
        description="Pinned waving cloth carrying a flag, text, or custom ASCII art.",
        presets={
            "flag": ClothSettings(),
            "checker": ClothSettings(pattern="checker"),
            "banner": ClothSettings(pattern="text"),
        },
    )
    effect_registry.register(
        "terrain",
        TerrainEffect,
        settings_cls=TerrainSettings,
        description="Perspective flyover of seeded hills with shaded or contour rendering.",
        presets={
            "hills": TerrainSettings(),
            "mountains": TerrainSettings(roughness=1.2, scale=0.08),
            "contours": TerrainSettings(style="contours"),
        },
    )


_populate()
