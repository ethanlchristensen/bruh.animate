"""Simulation behavior and public controls; no terminal or physical devices."""

from copy import deepcopy

import numpy as np
import pytest

from bruhanimate import (
    Buffer,
    ClothEffect,
    ClothSettings,
    DiffusionEffect,
    DiffusionSettings,
    MetaballsEffect,
    MetaballsSettings,
    SmokeEffect,
    SmokeSettings,
    TerrainEffect,
    TerrainSettings,
    WaterEffect,
    WaterSettings,
    effect_registry,
)
from bruhanimate.demos.nature_demo import build_scene


def test_water_impulses_travel_interfere_and_decay():
    settings = WaterSettings(drop_chance=0, damping=0.97, color=False)
    left = WaterEffect(Buffer(25, 41), " ", settings)
    right = WaterEffect(Buffer(25, 41), " ", settings)
    together = WaterEffect(Buffer(25, 41), " ", settings)
    left.drop(12, 12)
    right.drop(28, 12, -1)
    together.drop(12, 12)
    together.drop(28, 12, -1)
    assert left._height[12, 20] == 0
    for _ in range(25):
        for effect in (left, right, together):
            effect.update(1 / 30)
    assert abs(left._height[12, 20]) > 1e-5
    np.testing.assert_allclose(
        together._height, left._height + right._height, atol=1e-12
    )
    energy = np.linalg.norm(left._height)
    for _ in range(400):
        left.update(1 / 30)
    assert np.linalg.norm(left._height) < energy / 10


def test_water_stillness_and_resize_preserve_displacement_and_velocity():
    effect = WaterEffect(Buffer(8, 12), " ", WaterSettings(drop_chance=0))
    effect.update(1 / 30)
    assert not effect._height.any()
    effect.drop(6, 4)
    effect.update(1 / 30)
    height, previous = effect._height.copy(), effect._previous.copy()
    effect.resize((20, 10))
    np.testing.assert_array_equal(effect._height[:8, :12], height)
    np.testing.assert_array_equal(effect._previous[:8, :12], previous)
    assert not effect._height[8:].any()
    before = effect._height.copy()
    effect.drop(-1, 0)
    np.testing.assert_array_equal(before, effect._height)


@pytest.mark.parametrize(
    "args,error",
    [
        ((True, 1), TypeError),
        ((1, 2.0), TypeError),
        ((1, 1, True), TypeError),
        ((1, 1, float("nan")), ValueError),
        ((1, 1, 6), ValueError),
    ],
)
def test_water_validates_impulses(args, error):
    effect = WaterEffect(Buffer(3, 3), " ")
    with pytest.raises(error):
        effect.drop(*args)
    assert not effect._height.any()


@pytest.mark.parametrize("style", ["smoke", "ink"])
def test_smoke_travels_in_configured_direction_and_solid_wall_blocks_it(style):
    settings = SmokeSettings(style=style, turbulence=0, seed=2)
    open_effect = SmokeEffect(Buffer(15, 25), " ", settings)
    blocked = SmokeEffect(Buffer(15, 25), " ", settings)
    blocked.set_obstacles((x, 7) for x in range(25))
    for _ in range(100):
        open_effect.update(1 / 30)
        blocked.update(1 / 30)
    far = 3 if style == "smoke" else 11
    assert open_effect._density[far].sum() > 0.01
    assert blocked._density[far].sum() == 0
    assert not blocked._density[7].any()
    assert np.isfinite(blocked._density).all()
    density, mask = blocked._density.copy(), blocked._obstacles.copy()
    blocked.resize((30, 20))
    np.testing.assert_array_equal(blocked._density[:15, :25], density)
    np.testing.assert_array_equal(blocked._obstacles[:15, :25], mask)
    assert not blocked._density[15:].any()


def test_smoke_obstacle_replacement_is_atomic_and_copies_input():
    effect = SmokeEffect(Buffer(8, 10), " ")
    cells = [(1, 2), (-1, 0), (30, 20)]
    effect.set_obstacles(cells)
    cells.clear()
    assert effect._obstacles.sum() == 1
    with pytest.raises(TypeError):
        effect.set_obstacles([(0, 0), (2.5, 3)])
    assert effect._obstacles[2, 1] and effect._obstacles.sum() == 1
    effect.set_obstacles([])
    assert not effect._obstacles.any()


def test_metaballs_merge_through_additive_fields():
    settings = MetaballsSettings(count=2, radius=0.4, speed=0, color=False)
    effect = MetaballsEffect(Buffer(21, 41), " ", settings)
    # Two symmetric centers, each individually below the isosurface at center.
    effect._offsets[:] = [[-np.pi / 4, 0], [np.pi / 4, 0]]
    merged = effect._field()
    assert 1 < merged[10, 20] < 2
    effect.update(0)
    assert effect.buffer.buffer[10][20] != " "


@pytest.mark.parametrize(
    "name,settings",
    [
        ("metaballs", MetaballsSettings(speed=0, seed=4)),
        ("cloth", ClothSettings(speed=0)),
        ("terrain", TerrainSettings(speed=0, seed=4)),
    ],
)
def test_zero_speed_freezes_motion_and_resize_roundtrip_keeps_phase(name, settings):
    effect = effect_registry.create(name, Buffer(16, 40), " ", settings=settings)
    initial = deepcopy(effect.buffer.buffer)
    for _ in range(3):
        effect.update(1 / 30)
    assert effect.buffer.buffer == initial
    effect.resize((60, 24))
    effect.resize((40, 16))
    assert effect.buffer.buffer == initial


def test_cloth_copies_art_and_keeps_left_edge_pinned():
    rows = ["ABC", "D"]
    effect = ClothEffect(Buffer(24, 60), " ", ClothSettings(color=False), image=rows)
    rows[0] = "XXX"
    assert effect._image == ("ABC", "D  ")
    before = deepcopy(effect.buffer.buffer)
    for _ in range(14):
        effect.update(1 / 30)
    assert effect.buffer.buffer != before
    pinned = 60 // 12
    assert [row[pinned] for row in effect.buffer.buffer] == [
        row[pinned] for row in before
    ]
    text = "".join("".join(row) for row in effect.buffer.buffer)
    assert all(char in text for char in "ABCD")
    effect.resize((80, 30))
    assert effect._image == ("ABC", "D  ")
    effect.set_image(None)
    assert effect._image is None


@pytest.mark.parametrize(
    "image,error",
    [
        ([], ValueError),
        ("", ValueError),
        ([""], ValueError),
        ([42], TypeError),
        (object(), TypeError),
        ("\x1b[31mX", ValueError),
        ("界", ValueError),
        ("e\u0301", ValueError),
    ],
)
def test_cloth_rejects_unsupported_art_without_replacing_it(image, error):
    effect = ClothEffect(Buffer(8, 20), " ", image="OK")
    with pytest.raises(error):
        effect.set_image(image)
    assert effect._image == ("OK",)


@pytest.mark.parametrize("text", ["", "\n", "界", "\x1b", "e\u0301"])
def test_cloth_settings_validate_text(text):
    with pytest.raises(ValueError):
        ClothSettings(text=text)


def test_terrain_has_sky_and_varied_land_and_moves_without_reseeding():
    effect = TerrainEffect(Buffer(30, 80), " ", TerrainSettings(seed=42, color=False))
    before, noise = deepcopy(effect.buffer.buffer), effect._noise.copy()
    cells = {cell for row in before for cell in row}
    assert " " in cells and len(cells) >= 4
    for _ in range(40):
        effect.update(1 / 30)
    assert effect.buffer.buffer != before
    np.testing.assert_array_equal(effect._noise, noise)
    travel = effect._travel
    effect.resize((120, 40))
    assert effect._travel == travel
    np.testing.assert_array_equal(effect._noise, noise)


def test_diffusion_scattered_seeds_survive_and_rates_validate_atomically():
    effect = DiffusionEffect(
        Buffer(20, 48),
        " ",
        DiffusionSettings(seed=7, shading=True, seed_pattern="scattered", color=False),
    )
    for _ in range(180):
        effect.update(1 / 30)
    assert effect._V.max() > 0.2
    assert np.isfinite(effect._U).all() and np.isfinite(effect._V).all()
    assert len({c for row in effect.buffer.buffer for c in row}) >= 4
    original = effect.f, effect.k
    with pytest.raises(ValueError):
        effect.set_parameters(f=0.01, k=float("nan"))
    assert (effect.f, effect.k) == original
    effect.set_parameters(k=0.065)
    assert effect.f == original[0] and effect.k == 0.065


def test_diffusion_new_fields_keep_positional_settings_and_seed_tiny_surfaces():
    settings = DiffusionSettings(False, "X", 0.035, 0.065, 4)
    assert settings.char == "X" and settings.steps_per_frame == 4
    effect = DiffusionEffect(Buffer(1, 1), " ", DiffusionSettings(seed=1))
    assert effect._V[0, 0] > 0.2


@pytest.mark.parametrize("name", ["water", "smoke", "metaballs", "cloth", "terrain"])
def test_new_effects_render_valid_cells_and_update_without_mutating_prior_draw(name):
    from bruhanimate.grid import _glyph

    effect = effect_registry.create(name, Buffer(12, 30), " ", seed=5)
    for _ in range(30):
        effect.update(1 / 30)
    frame = Buffer(12, 30)
    effect.draw(frame)
    saved = deepcopy(frame.buffer)
    effect.update(1 / 30)
    assert frame.buffer == saved
    for row in saved:
        for cell in row:
            _glyph(str(cell))


def test_nature_gallery_survives_hidden_slots_and_resize_without_restarting(
    monkeypatch,
):
    from bruhanimate import BaseEffect

    starts = []
    original = BaseEffect.start

    def start(effect):
        starts.append(effect)
        original(effect)

    monkeypatch.setattr(BaseEffect, "start", start)
    scene = build_scene(Buffer(1, 1))
    scene.start()
    try:
        scene.resize((120, 40))
        scene.update(1 / 30)
        assert len(starts) == 6
        originals = tuple(starts)
        for size in ((1, 1), (150, 45), (80, 24)):
            scene.resize(size)
            scene.update(1 / 30)
            target = Buffer(size[1], size[0])
            scene.draw(target)
        assert tuple(starts) == originals
    finally:
        scene.close()
    assert all(not effect._started for effect in starts)
