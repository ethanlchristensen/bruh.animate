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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Type

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
        """Register an effect under *name*."""
        self._registry[name] = EffectEntry(
            name=name,
            effect_cls=effect_cls,
            settings_cls=settings_cls,
            description=description,
            presets=presets or {},
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
        """Return the preset dict for the named effect."""
        return dict(self.get(name).presets)

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
        settings: Any = None,
        preset: str | None = None,
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

        if settings is None and preset is not None:
            if preset not in entry.presets:
                raise KeyError(
                    f"Preset '{preset}' not found for '{name}'. "
                    f"Available: {sorted(entry.presets)}"
                )
            settings = deepcopy(entry.presets[preset])

        if settings is not None and entry.settings_cls is not None:
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
    from .diffusion_effect import DiffusionEffect
    from .draw_lines_effect import DrawLinesEffect
    from .fire_effect import FireEffect
    from .firework_effect import FireworkEffect
    from .game_of_life_effect import GameOfLifeEffect
    from .julia_effect import JuliaEffect
    from .matrix_effect import MatrixEffect
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
        DiffusionSettings,
        DrawLinesSettings,
        FireSettings,
        FireworkSettings,
        GameOfLifeSettings,
        MatrixSettings,
        NoiseSettings,
        OffsetSettings,
        PerlinSettings,
        PlasmaSettings,
        RainSettings,
        SandSettings,
        SnowSettings,
        StarSettings,
        TwinkleSettings,
        VoronoiSettings,
    )
    from .snow_effect import SnowEffect
    from .star_effect import StarEffect
    from .static_effect import StaticEffect
    from .twinkle_effect import TwinkleEffect
    from .voronoi_effect import VoronoiEffect

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
            "up": OffsetSettings(direction="up"),
            "down": OffsetSettings(direction="down"),
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
        description="System audio visualizer (bars, mirror, waveform, spectrum, radial, rain, tunnel, ripple, vortex, wave, starfield, fireworks, interference, bounce, lightning, aurora, orbit, scope, grid, helix, lissajous, sunburst, mandala, comet, weave).",
        presets={
            "bars": AudioSettings(mode="bars", color=True, smoothing=0.25),
            "mirror": AudioSettings(mode="mirror", color=True, smoothing=0.25),
            "waveform": AudioSettings(mode="waveform", color=True, smoothing=0.1),
            "spectrum": AudioSettings(mode="spectrum", color=True, smoothing=0.2),
            "radial": AudioSettings(mode="radial", color=True, smoothing=0.3),
            "rain": AudioSettings(mode="rain", color=True, smoothing=0.2),
            "minimal": AudioSettings(mode="bars", color=False, smoothing=0.6),
            "tunnel": AudioSettings(mode="tunnel", color=True, smoothing=0.2),
            "ripple": AudioSettings(
                mode="ripple", color=True, smoothing=0.15, sensitivity=1.5
            ),
            "vortex": AudioSettings(mode="vortex", color=True, smoothing=0.2),
            "wave": AudioSettings(mode="wave", color=True, smoothing=0.25),
            "starfield": AudioSettings(mode="starfield", color=True, smoothing=0.2),
            "fireworks": AudioSettings(
                mode="fireworks", color=True, smoothing=0.15, sensitivity=2.0
            ),
            "interference": AudioSettings(
                mode="interference", color=True, smoothing=0.2
            ),
            "bounce": AudioSettings(mode="bounce", color=True, smoothing=0.2),
            "lightning": AudioSettings(
                mode="lightning", color=True, smoothing=0.1, sensitivity=1.5
            ),
            "aurora": AudioSettings(mode="aurora", color=True, smoothing=0.3),
            "orbit": AudioSettings(mode="orbit", color=True, smoothing=0.2),
            "orbit_gradient": AudioSettings(
                mode="orbit_gradient", color=True, smoothing=0.2
            ),
            "scope": AudioSettings(
                mode="scope", color=True, smoothing=0.0, sensitivity=3.0
            ),
            "grid": AudioSettings(mode="grid", color=True, smoothing=0.2),
            "helix": AudioSettings(mode="helix", color=True, smoothing=0.25),
            "lissajous": AudioSettings(mode="lissajous", color=True, smoothing=0.2),
            "sunburst": AudioSettings(mode="sunburst", color=True, smoothing=0.2),
            "mandala": AudioSettings(mode="mandala", color=True, smoothing=0.25),
            "comet": AudioSettings(
                mode="comet", color=True, smoothing=0.15, sensitivity=1.5
            ),
            "weave": AudioSettings(mode="weave", color=True, smoothing=0.2),
        },
    )


_populate()
