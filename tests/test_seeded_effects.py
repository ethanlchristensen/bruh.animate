import json
import random
from pathlib import Path

import numpy as np
import pytest

from bruhanimate import (
    Buffer,
    Firework,
    NoiseSettings,
    SnowSettings,
    effect_registry,
    effects,
)
from bruhanimate.bruheffect.audio_effect import AudioEffect
from bruhanimate.bruhutil.bruhtypes import valid_firework_types

CASES = [
    pytest.param(name, preset, id=f"{name}-{preset or 'default'}")
    for name, entry in effect_registry.entries().items()
    if entry.settings_cls is not None
    for preset in [None, *entry.presets]
]


@pytest.mark.parametrize("name, preset", CASES)
def test_seeds_reproduce_interleaved_effects_without_global_rng(
    name, preset, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("effect used a process-global RNG")

    for module in (random, np.random):
        for method in ("random", "randint", "uniform", "choice", "seed", "shuffle"):
            monkeypatch.setattr(module, method, forbidden)
    # Construction, including NumPy fields, must be repeatable as well as updates.
    first = effect_registry.create(name, Buffer(8, 16), " ", preset=preset, seed=73)
    other = effect_registry.create("noise", Buffer(8, 16), " ", seed=9)
    second = effect_registry.create(name, Buffer(8, 16), " ", preset=preset, seed=73)
    if isinstance(first, AudioEffect):
        # Identical prerecorded input; never call start or acquire audio hardware.
        audio = np.sin(np.arange(first._audio_chunk.size) * 0.13).astype(np.float32)
        first._audio_chunk = audio.copy()
        second._audio_chunk = audio.copy()
    try:
        for _ in range(12):
            first.update(1 / 30)
            other.update(1 / 30)
            second.update(1 / 30)
            left, right = Buffer(8, 16), Buffer(8, 16)
            before = first.rng.getstate(), first.np_rng.bit_generator.state
            first.draw(left)
            first.draw(left)
            assert before == (first.rng.getstate(), first.np_rng.bit_generator.state)
            second.draw(right)
            assert left.buffer == right.buffer
    finally:
        first.close()
        second.close()
        other.close()


@pytest.mark.parametrize("burst", valid_firework_types)
def test_firework_children_share_seeded_stream(burst):
    first = Firework(
        burst,
        8,
        16,
        color_enabled=True,
        firework_color_type="random",
        rng=random.Random(42),
    )
    second = Firework(
        burst,
        8,
        16,
        color_enabled=True,
        firework_color_type="random",
        rng=random.Random(42),
    )
    first.create_particles()
    second.create_particles()
    assert len(first.particles) == len(second.particles)
    for a, b in zip(first.particles, second.particles):
        assert a.rng is first.rng
        assert b.rng is second.rng
        a.update()
        b.update()
        assert (a.x, a.y, a.life, a.symbol) == (b.x, b.y, b.life, b.symbol)


def test_seed_overrides_do_not_mutate_settings_or_presets():
    settings = SnowSettings(seed=10, intensity=0.7)
    resolved = effect_registry.resolve_settings(
        "snow", settings=settings, preset="light", seed=20
    )
    assert resolved.seed == 20 and resolved.intensity == 0.7
    assert settings.seed == 10
    assert effects.snow.preset("light").seed is None
    assert effect_registry.resolve_settings("snow", settings=settings).seed == 10


@pytest.mark.parametrize(
    "seed, error",
    [(-1, ValueError), (True, TypeError), (1.5, TypeError), ("42", TypeError)],
)
def test_invalid_seeds_fail_early(seed, error):
    with pytest.raises(error, match="seed"):
        SnowSettings(seed=seed)
    with pytest.raises(error, match="seed"):
        effect_registry.resolve_settings("snow", seed=seed)


def test_seed_preserves_existing_positional_settings_arguments():
    assert NoiseSettings(500, seed=0).intensity == 500


def test_different_seeds_change_random_output():
    first, second = [], []
    effects.noise.capture(seed=1, on_frame=first.append, frames=2, width=20, height=10)
    effects.noise.capture(seed=2, on_frame=second.append, frames=2, width=20, height=10)
    assert first != second


def test_seeded_ascii_visual_regressions():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "seeded_frames.json").read_text(
            encoding="utf-8"
        )
    )
    for name, expected in fixture.items():
        frames = []
        getattr(effects, name).capture(
            seed=42, on_frame=frames.append, frames=12, width=16, height=6
        )
        assert [frames[index].text().splitlines() for index in (0, 4, 11)] == expected
