"""Static API contract; run mypy, do not execute this file."""

from typing import assert_type

from bruhanimate import (
    Frame,
    RainSettings,
    SnowSettings,
    capture,
    effects,
    play,
    record,
)
from bruhanimate.effects import SnowPreset

assert_type(effects.snow.defaults(), SnowSettings)
assert_type(effects.snow.preset("light"), SnowSettings)
assert_type(effects.snow.presets(), dict[SnowPreset, SnowSettings])
assert_type(effects.static.defaults(), None)
assert_type(effects.snow.play(preset="light", duration=1), int)
effects.snow.play(settings=SnowSettings(wind=0.5), fps=60, updates_per_second=30)
play("snow", preset="light", duration=1)
play("custom_registered_effect", settings=object(), duration=1)

# warn_unused_ignores makes these checks fail if hints degrade to Any or str.
effects.snow.play(preset="storm")  # type: ignore[arg-type]
effects.snow.preset("storm")  # type: ignore[arg-type]
effects.snow.play(settings=RainSettings())  # type: ignore[arg-type]
effects.static.play(preset="light")  # type: ignore[arg-type]
SnowSettings(wind="strong")  # type: ignore[arg-type]
RainSettings(wind_direction="north")  # type: ignore[arg-type]

frames: list[Frame] = []
assert_type(capture("snow", on_frame=frames.append, frames=2, seed=42), int)
assert_type(
    effects.snow.capture(preset="light", on_frame=frames.append, frames=2, seed=42), int
)
assert_type(effects.snow.record("snow.cast", preset="light", duration=2, seed=42), int)
assert_type(record("snow", "snow.cast", frames=2), int)
assert_type(frames[0].cells, tuple[tuple[str, ...], ...])
assert_type(frames[0].time, float)
assert_type(SnowSettings(seed=42).seed, int | None)
effects.snow.capture(on_frame=frames.append, preset="storm", frames=1)  # type: ignore[arg-type]
effects.snow.record("snow.cast", settings=RainSettings(), frames=1)  # type: ignore[arg-type]
effects.snow.record("snow.cast", preset="storm", frames=1)  # type: ignore[arg-type]
SnowSettings(seed="42")  # type: ignore[arg-type]
frames[0].time = 1.0  # type: ignore[misc]
