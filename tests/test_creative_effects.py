"""Deterministic simulation, depth, recycling, budgets and raster ownership."""

from copy import deepcopy

import numpy as np
import pytest

from bruhanimate import (
    Buffer,
    FlowEffect,
    FlowSettings,
    GrowthEffect,
    GrowthSettings,
    StarfieldEffect,
    StarfieldSettings,
    effect_registry,
)
from bruhanimate.grid import _glyph


@pytest.mark.parametrize("name", ["flow", "growth", "starfield"])
@pytest.mark.parametrize("size", [(1, 1), (5, 3), (60, 20)])
def test_new_effects_survive_many_generations_and_draw_is_pure(name, size):
    effect = effect_registry.create(name, Buffer(size[1], size[0]), " ", seed=7)
    effect.start()
    try:
        for _ in range(220):
            effect.update(1 / 30)
        assert np.isfinite(effect._trail).all()
        assert 0 <= effect._trail.min() <= effect._trail.max() <= 1
        first, second = Buffer(size[1], size[0]), Buffer(size[1], size[0])
        state = effect.rng.getstate(), deepcopy(effect.np_rng.bit_generator.state)
        effect.draw(first)
        effect.draw(second)
        assert first.buffer == second.buffer
        assert state == (effect.rng.getstate(), effect.np_rng.bit_generator.state)
        saved = deepcopy(first.buffer)
        effect.update(1 / 30)
        assert first.buffer == saved
        for row in saved:
            for cell in row:
                _glyph(cell)
    finally:
        effect.close()
        effect.close()


@pytest.mark.parametrize("name", ["flow", "growth", "starfield"])
def test_zero_speed_freezes_and_settings_are_copied(name):
    settings = effect_registry.get(name).settings_cls(speed=0, seed=7)
    effect = effect_registry.create(name, Buffer(10, 20), " ", settings=settings)
    before = deepcopy(effect.buffer.buffer)
    state = effect.rng.getstate(), deepcopy(effect.np_rng.bit_generator.state)
    settings.speed = 1
    for _ in range(4):
        effect.update(1 / 30)
    assert effect.buffer.buffer == before
    assert state == (effect.rng.getstate(), effect.np_rng.bit_generator.state)


def test_flow_wrap_does_not_paint_across_the_screen_and_resize_preserves_overlap():
    effect = FlowEffect(Buffer(10, 100), " ", FlowSettings(count=1, seed=1))
    effect._points[:] = [[99.9, 5]]
    effect.update(1 / 30)
    assert not effect._trail[:, 3:97].any()
    trail = effect._trail.copy()
    effect.resize((120, 12))
    np.testing.assert_array_equal(effect._trail[:10, :100], trail)
    assert not effect._trail[10:].any()
    effect.resize((1, 1))
    assert ((effect._points >= 0) & (effect._points < 1)).all()


def test_growth_tip_budget_and_generation_restart_are_bounded():
    effect = GrowthEffect(
        Buffer(200, 200),
        " ",
        GrowthSettings(
            roots=32, max_tips=32, speed=0.1, branch_chance=1, cycle_ticks=12, seed=2
        ),
    )
    for _ in range(12):
        effect.update(1 / 30)
        assert len(effect._tips) == 32
    assert effect._age == 12
    effect.update(1 / 30)
    assert effect._age == 1
    assert len(effect._tips) <= 32
    # A shrink can remove every live tip; resize itself must not plant new ones.
    state = effect.rng.getstate()
    effect.resize((1, 1))
    assert effect.rng.getstate() == state
    assert not effect._tips
    effect.update(1 / 30)
    assert effect._age == 1
    assert effect._trail[0, 0] == 1


def test_growth_with_no_branching_keeps_root_budget_and_draws_upwards():
    effect = GrowthEffect(
        Buffer(40, 60), " ", GrowthSettings(roots=2, branch_chance=0, seed=2)
    )
    for _ in range(40):
        effect.update(1 / 30)
    assert len(effect._tips) <= 2
    assert effect._trail[:30].any()
    assert not effect._trail[:15].any()


def test_star_projection_expands_with_depth_and_nearer_star_wins_overlap():
    effect = StarfieldEffect(Buffer(20, 80), " ", StarfieldSettings(count=2, seed=1))
    effect._stars[:] = [[0.2, 0, 0.8], [0.2, 0, 0.4]]
    points = effect._project()
    assert points[1, 0] - 40 == pytest.approx(2 * (points[0, 0] - 40))
    effect._stars[:] = [[0, 0, 0.2], [0, 0, 0.8]]
    effect.resize((80, 20))
    assert effect._trail[10, 40] == pytest.approx(0.85)
    stars = effect._stars.copy()
    state = deepcopy(effect.np_rng.bit_generator.state)
    effect.resize((40, 10))
    np.testing.assert_array_equal(effect._stars, stars)
    assert effect.np_rng.bit_generator.state == state
    assert np.count_nonzero(effect._trail) == 1
    assert effect._trail[5, 20] == pytest.approx(0.85)


def test_star_recycling_never_connects_old_position_or_divides_by_zero():
    effect = StarfieldEffect(
        Buffer(20, 80), " ", StarfieldSettings(count=1, speed=0.2, trails=0.8, seed=4)
    )
    effect._trail[:] = 0
    effect._stars[:] = [[-0.1, 0, 0.2]]
    with np.errstate(all="raise"):
        effect.update(1 / 30)
    assert effect._stars[0, 2] == 1
    assert np.count_nonzero(effect._trail) == 1


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (FlowSettings, {"count": 2001}),
        (FlowSettings, {"scale": 0}),
        (FlowSettings, {"decay": 1}),
        (GrowthSettings, {"roots": 33}),
        (GrowthSettings, {"roots": 4, "max_tips": 3}),
        (GrowthSettings, {"cycle_ticks": 0}),
        (GrowthSettings, {"branch_chance": 1.1}),
        (StarfieldSettings, {"zoom": 0}),
        (StarfieldSettings, {"twist": float("nan")}),
        (StarfieldSettings, {"speed": -1}),
    ],
)
def test_invalid_settings_fail_before_allocating(cls, kwargs):
    with pytest.raises(ValueError):
        cls(**kwargs)
