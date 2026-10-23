import random

import numpy as np
import pytest

from bruhanimate import Buffer, effect_registry
from bruhanimate.bruheffect.audio_effect import AudioEffect
from bruhanimate.bruheffect.firework_effect import FireworkEffect
from bruhanimate.bruheffect.rain_effect import RainEffect
from bruhanimate.bruheffect.settings import (
    AudioSettings,
    FireworkSettings,
    RainSettings,
    SnowSettings,
)
from bruhanimate.bruheffect.snow_effect import SnowEffect

EFFECT_CASES = [
    pytest.param(name, preset, id=f"{name}-{preset or 'default'}")
    for name, entry in effect_registry.entries().items()
    for preset in [None, *entry.presets]
]


@pytest.fixture(autouse=True)
def isolated_randomness_and_audio(monkeypatch):
    """Keep smoke tests reproducible without accessing audio hardware."""
    random_state = random.getstate()
    numpy_state = np.random.get_state()
    random.seed(0)
    np.random.seed(0)
    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    try:
        yield
    finally:
        random.setstate(random_state)
        np.random.set_state(numpy_state)


@pytest.mark.parametrize("size", [(24, 80), (3, 5), (1, 1)])
@pytest.mark.parametrize("name, preset", EFFECT_CASES)
def test_registered_effects_render_at_representative_sizes(name, preset, size):
    buffer = Buffer(*size)
    effect = effect_registry.create(name, buffer, " ", preset=preset)
    try:
        for frame in range(12):
            effect.update(1 / 30)
            assert len(buffer.buffer) == size[0]
            assert all(len(row) == size[1] for row in buffer.buffer)
            first, second = Buffer(*size), Buffer(*size)
            effect.draw(first)
            effect.draw(second)
            assert first.buffer == second.buffer
            assert all(isinstance(cell, str) for row in first.buffer for cell in row)
    finally:
        if isinstance(effect, AudioEffect):
            effect.stop()


@pytest.mark.parametrize("name", ["stars", "gol"])
def test_color_presets_produce_colored_cells(name, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    effect = effect_registry.create(name, Buffer(3, 5), " ", preset="color")

    effect.update(1 / 30)

    assert any("\x1b[" in str(cell) for row in effect.buffer.buffer for cell in row)


@pytest.mark.parametrize(
    "preset", [None, "drizzle", "storm", "thunderstorm", "monsoon"]
)
def test_rain_defaults_and_presets_can_draw_visible_rain(preset, monkeypatch):
    effect = effect_registry.create("rain", Buffer(3, 5), " ", preset=preset)
    # Select the last population character so this cannot pass or fail by chance.
    monkeypatch.setattr(random, "randint", lambda low, high: high)
    monkeypatch.setattr(random, "random", lambda: 1.0)

    effect.update(1 / 30)

    assert any(cell != " " for cell in effect.buffer.buffer[0])


@pytest.mark.parametrize("intensity", [1, 50, 100, 600, 999])
def test_positive_rain_intensity_can_draw_rain(intensity, monkeypatch):
    effect = RainEffect(Buffer(3, 5), " ", RainSettings(intensity=intensity))
    monkeypatch.setattr(random, "randint", lambda low, high: high)

    effect.update(1 / 30)

    assert any(cell != " " for cell in effect.buffer.buffer[0])


def test_zero_rain_intensity_is_dry():
    effect = RainEffect(Buffer(3, 5), " ", RainSettings(intensity=0))
    for frame in range(4):
        effect.update(1 / 30)

    assert effect.buffer.buffer == [[" "] * 5 for _ in range(3)]


@pytest.mark.parametrize("intensity, expected", [(-1, 0), (1000, 999)])
def test_rain_intensity_bounds_match_for_constructor_and_setter(intensity, expected):
    effect = RainEffect(Buffer(3, 5), " ", RainSettings(intensity=intensity))
    assert effect.intensity == expected

    effect.set_intensity(intensity)
    assert effect.intensity == expected


@pytest.mark.parametrize("intensity", [900, 999])
def test_rain_swells_turn_back_at_or_above_the_upper_limit(intensity):
    effect = RainEffect(
        Buffer(3, 5), " ", RainSettings(intensity=intensity, swells=True)
    )

    effect.update(1 / 30)

    assert effect.intensity == intensity - 1


@pytest.mark.parametrize("width", [1, 2, 3, 4, 5])
def test_lightning_stays_inside_narrow_buffers(width):
    effect = RainEffect(
        Buffer(3, width),
        " ",
        RainSettings(intensity=600, lightning=True, lightning_chance=1),
    )

    effect.update(1 / 30)

    assert effect._bolts
    assert all(
        0 <= x < width and 0 <= y < 3 for cells, _ in effect._bolts for x, y, _ in cells
    )
    assert any(cell != " " for row in effect.buffer.buffer for cell in row)


def test_light_snow_is_less_dense_than_default_snow(monkeypatch):
    light = effect_registry.create("snow", Buffer(3, 5), " ", preset="light")
    default = SnowEffect(Buffer(3, 5), " ")
    monkeypatch.setattr(random, "random", lambda: 0.0075)

    light.update(1 / 30)
    default.update(1 / 30)

    assert not light.flakes
    assert len(default.flakes) == 5


@pytest.mark.parametrize("use_setter", [False, True])
def test_snow_can_be_disabled(use_setter, monkeypatch):
    effect = SnowEffect(Buffer(3, 5), " ", SnowSettings(intensity=0))
    if use_setter:
        effect.set_snow_intensity(0.5)
        effect.set_snow_intensity(0)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    effect.update(1 / 30)

    assert not effect.flakes
    assert effect.buffer.buffer == [[" "] * 5 for _ in range(3)]


@pytest.mark.parametrize("height", [1, 2, 3, 9, 10])
def test_fireworks_can_spawn_and_explode_in_short_buffers(height):
    effect = FireworkEffect(Buffer(height, 3), " ", FireworkSettings(rate=1))

    effect.update(1 / 30)
    first_firework = effect.fireworks[0]
    for frame in range(1, 5):
        effect.update(1 / 30)

    assert first_firework.exploded
    assert all(len(row) == 3 for row in effect.buffer.buffer)


@pytest.mark.parametrize("size", [(1, 1), (1, 5), (5, 1)])
def test_radial_audio_can_draw_when_one_dimension_is_a_single_cell(size):
    effect = AudioEffect(Buffer(*size), " ", AudioSettings(mode="radial"))
    effect._audio_chunk = np.ones_like(effect._audio_chunk)
    try:
        effect.update(1 / 30)

        assert any(cell != " " for row in effect.buffer.buffer for cell in row)
    finally:
        effect.stop()
