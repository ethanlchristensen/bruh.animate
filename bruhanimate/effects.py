"""Discover built-in effects with editor completion and effect-specific types.

Type ``effects.`` to browse effects, then ``effects.snow.play(preset=...)``
for snow preset completion. ``effects.snow.presets()`` explains the presets by
returning independent SnowSettings copies. Runtime extensions remain available
through ``effect_registry`` and ``play("custom_name", ...)``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from typing import Generic, Literal, Never, TextIO, TypeVar, cast

from .bruheffect.registry import EffectEntry, effect_registry
from .bruheffect.settings import (
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
from .bruhutil.bruhtypes import EffectType as EffectName
from .capture import Frame

SettingsT = TypeVar("SettingsT")
PresetT = TypeVar("PresetT", bound=str)


@dataclass(frozen=True)
class EffectInfo(Generic[SettingsT, PresetT]):
    """Typed view of a registry entry, without constructing a running effect."""

    name: EffectName

    @property
    def description(self) -> str:
        """Human-readable description from the live registry."""
        return effect_registry.get(self.name).description

    def defaults(self) -> SettingsT:
        """Return a fresh default configuration, or None for unconfigured effects."""
        cls = effect_registry.get(self.name).settings_cls
        return cast(SettingsT, cls() if cls is not None else None)

    def presets(self) -> dict[PresetT, SettingsT]:
        """Return preset names and independent, editable configuration copies."""
        return cast(dict[PresetT, SettingsT], effect_registry.presets(self.name))

    def preset(self, name: PresetT) -> SettingsT:
        """Return one preset's settings; editors suggest this effect's names."""
        return cast(SettingsT, effect_registry.resolve_settings(self.name, preset=name))

    def play(
        self,
        *,
        preset: PresetT | None = None,
        settings: SettingsT | None = None,
        seed: int | None = None,
        fps: float | None = 30,
        updates_per_second: float | None = None,
        frames: int | None = None,
        duration: float | None = None,
        on_complete: Literal["hold", "exit"] = "hold",
        background: str = " ",
        event_handler: Callable[[int], bool] | None = None,
    ) -> int:
        """Play this effect with typed presets/settings through the shared player.

        duration is wall-clock seconds after startup; None is unlimited and zero
        starts no effect. See bruhanimate.play for timing and ownership details.
        """
        from .player import play

        return play(
            self.name,
            preset=preset,
            settings=settings,
            seed=seed,
            fps=fps,
            updates_per_second=updates_per_second,
            frames=frames,
            duration=duration,
            on_complete=on_complete,
            background=background,
            event_handler=event_handler,
        )

    def capture(
        self,
        *,
        on_frame: Callable[[Frame], None],
        preset: PresetT | None = None,
        settings: SettingsT | None = None,
        seed: int | None = None,
        width: int = 80,
        height: int = 24,
        fps: float = 30,
        updates_per_second: float | None = None,
        frames: int | None = None,
        duration: float | None = None,
        on_complete: Literal["hold", "exit"] = "exit",
        background: str = " ",
    ) -> int:
        """Stream immutable frames with typed presets/settings and virtual timing.

        Requires frames or duration; see bruhanimate.capture for lifecycle,
        reproducibility and timing details. seed overrides the selected settings.
        """
        from .capture import capture

        return capture(
            self.name,
            on_frame=on_frame,
            preset=preset,
            settings=settings,
            seed=seed,
            width=width,
            height=height,
            fps=fps,
            updates_per_second=updates_per_second,
            frames=frames,
            duration=duration,
            on_complete=on_complete,
            background=background,
        )

    def record(
        self,
        output: str | PathLike[str] | TextIO,
        *,
        preset: PresetT | None = None,
        settings: SettingsT | None = None,
        seed: int | None = None,
        width: int = 80,
        height: int = 24,
        fps: float = 30,
        updates_per_second: float | None = None,
        frames: int | None = None,
        duration: float | None = None,
        on_complete: Literal["hold", "exit"] = "exit",
        background: str = " ",
        overwrite: bool = False,
    ) -> int:
        """Record an asciicast v2 file or borrowed text stream, without a terminal.

        Requires frames or duration; see bruhanimate.record. Existing files are
        protected unless overwrite=True. Preset/settings hints match this effect.
        """
        from .capture import record

        return record(
            self.name,
            output,
            preset=preset,
            settings=settings,
            seed=seed,
            width=width,
            height=height,
            fps=fps,
            updates_per_second=updates_per_second,
            frames=frames,
            duration=duration,
            on_complete=on_complete,
            background=background,
            overwrite=overwrite,
        )


def names() -> list[str]:
    """List all currently registered names, including custom effects."""
    return effect_registry.names()


def get(name: str) -> EffectEntry:
    """Inspect a live registry entry, including custom effects."""
    return effect_registry.get(name)


static: EffectInfo[None, Never] = EffectInfo("static")
"""Fills the screen with a static background character."""

OffsetPreset = Literal["right", "left"]
offset: EffectInfo[OffsetSettings, OffsetPreset] = EffectInfo("offset")
"""Scrolling offset background."""

NoisePreset = Literal["sparse", "dense", "color"]
noise: EffectInfo[NoiseSettings, NoisePreset] = EffectInfo("noise")
"""Random noise pixels."""

StarPreset = Literal["greyscale", "color"]
stars: EffectInfo[StarSettings, StarPreset] = EffectInfo("stars")
"""Blinking star field."""

PlasmaPreset = Literal["greyscale", "color", "blocks", "random"]
plasma: EffectInfo[PlasmaSettings, PlasmaPreset] = EffectInfo("plasma")
"""Animated sine-wave plasma."""

GameOfLifePreset = Literal["plain", "decay", "color"]
gol: EffectInfo[GameOfLifeSettings, GameOfLifePreset] = EffectInfo("gol")
"""Conway's Game of Life with optional color decay."""

RainPreset = Literal["drizzle", "storm", "thunderstorm", "monsoon"]
rain: EffectInfo[RainSettings, RainPreset] = EffectInfo("rain")
"""Falling rain with wind direction and collision."""

MatrixPreset = Literal["default", "fast"]
matrix: EffectInfo[MatrixSettings, MatrixPreset] = EffectInfo("matrix")
"""Cascading random-character digital rain."""

DrawLinesPreset = Literal["thin", "thick"]
drawlines: EffectInfo[DrawLinesSettings, DrawLinesPreset] = EffectInfo("drawlines")
"""Bresenham line drawing onto the buffer."""

SnowPreset = Literal["light", "moderate", "blizzard", "windy"]
snow: EffectInfo[SnowSettings, SnowPreset] = EffectInfo("snow")
"""Falling snow with wind and ground accumulation."""

TwinklePreset = Literal["sparse", "dense"]
twinkle: EffectInfo[TwinkleSettings, TwinklePreset] = EffectInfo("twinkle")
"""Characters that pulse in brightness."""

FireworkPreset = Literal["plain", "color", "random"]
firework: EffectInfo[FireworkSettings, FireworkPreset] = EffectInfo("firework")
"""Firework explosions with multiple burst patterns."""

FirePreset = Literal["campfire", "inferno", "windy"]
fire: EffectInfo[FireSettings, FirePreset] = EffectInfo("fire")
"""Particle-based fire simulation."""

julia: EffectInfo[None, Never] = EffectInfo("julia")
"""Animated Julia-set fractal."""

BoidsPreset = Literal["default", "dense", "fast"]
boids: EffectInfo[BoidsSettings, BoidsPreset] = EffectInfo("boids")
"""Reynolds flocking simulation: separation, alignment, and cohesion rules."""

SandPreset = Literal["light", "normal", "heavy"]
sand: EffectInfo[SandSettings, SandPreset] = EffectInfo("sand")
"""Falling-sand cellular automaton; particles spawn at the top and pile up."""

DiffusionPreset = Literal["coral", "spots", "stripes"]
diffusion: EffectInfo[DiffusionSettings, DiffusionPreset] = EffectInfo("diffusion")
"""Gray-Scott reaction-diffusion; produces evolving organic spots and stripes."""

AutomatonPreset = Literal["rule30", "rule90", "rule110", "rule184"]
automaton: EffectInfo[AutomatonSettings, AutomatonPreset] = EffectInfo("automaton")
"""Wolfram 1-D elementary cellular automaton scrolling downward."""

VoronoiPreset = Literal["slow", "fast", "dense"]
voronoi: EffectInfo[VoronoiSettings, VoronoiPreset] = EffectInfo("voronoi")
"""Animated Voronoi diagram with drifting seed points."""

PerlinPreset = Literal["sparse", "dense", "fast"]
perlin: EffectInfo[PerlinSettings, PerlinPreset] = EffectInfo("perlin")
"""Smooth animated noise field built from multiple sine-wave octaves."""

AudioPreset = Literal[
    "bars",
    "mirror",
    "waveform",
    "spectrum",
    "radial",
    "rain",
    "minimal",
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
audio: EffectInfo[AudioSettings, AudioPreset] = EffectInfo("audio")
"""System audio visualizer (bars, mirror, waveform, spectrum, radial, rain, tunnel, ripple, vortex, wave, starfield, fireworks, interference, bounce, lightning, aurora, orbit, scope, grid, helix, lissajous, sunburst, mandala, comet, weave)."""

__all__ = [
    "EffectInfo",
    "EffectName",
    "names",
    "get",
    "static",
    "OffsetPreset",
    "offset",
    "NoisePreset",
    "noise",
    "StarPreset",
    "stars",
    "PlasmaPreset",
    "plasma",
    "GameOfLifePreset",
    "gol",
    "RainPreset",
    "rain",
    "MatrixPreset",
    "matrix",
    "DrawLinesPreset",
    "drawlines",
    "SnowPreset",
    "snow",
    "TwinklePreset",
    "twinkle",
    "FireworkPreset",
    "firework",
    "FirePreset",
    "fire",
    "julia",
    "BoidsPreset",
    "boids",
    "SandPreset",
    "sand",
    "DiffusionPreset",
    "diffusion",
    "AutomatonPreset",
    "automaton",
    "VoronoiPreset",
    "voronoi",
    "PerlinPreset",
    "perlin",
    "AudioPreset",
    "audio",
]
