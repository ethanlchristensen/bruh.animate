"""State-aware resizing must relocate views without simulating another tick."""

from copy import deepcopy
from unittest.mock import Mock

import numpy as np
import pytest

from bruhanimate import (
    Buffer,
    Column,
    FireEffect,
    FireSettings,
    MatrixEffect,
    MatrixSettings,
    Panel,
    PlasmaEffect,
    PlasmaSettings,
    Playback,
    Player,
    RainEffect,
    RainSettings,
    Slot,
    SnowEffect,
    SnowSettings,
    effect_registry,
)
from bruhanimate.demos.dashboard_demo import build_scene, draw_state, solve


def snow(width=5, height=6):
    return SnowEffect(Buffer(height, width), " ", SnowSettings(intensity=0, seed=42))


def test_snow_floor_pile_moves_to_new_bottom_without_advancing_flakes():
    effect = snow()
    effect.ground_flakes[-1][1] = 18
    effect.ground_flakes[-2][1] = 4
    effect.generate_snowflake(3)
    flake = effect.flakes[0]
    flake.update(y=1, fall_delay=2)
    before_flake = dict(flake)
    rng = effect.rng.getstate()
    numpy_rng = deepcopy(effect.np_rng.bit_generator.state)
    effect.start()
    original = effect.buffer
    original_cells = deepcopy(original.buffer)

    effect.resize((8, 10))

    assert effect._started
    assert effect.buffer is not original and original.buffer == original_cells
    assert (effect.buffer.width(), effect.buffer.height()) == (8, 10)
    assert effect.ground_flakes[-1][1] == 18
    assert effect.ground_flakes[-2][1] == 4
    assert sum(map(sum, effect.ground_flakes)) == 22
    assert effect.buffer.get_char(1, 9) == "#"
    assert effect.buffer.get_char(1, 8) == "-"
    assert effect.buffer.get_char(1, 5) == " "
    assert effect.flakes == [before_flake] and effect.flakes[0] is flake
    assert effect.buffer.get_char(3, 1) == flake["colored"].colored
    assert len(effect.image_flakes) == 8
    assert effect.rng.getstate() == rng
    assert effect.np_rng.bit_generator.state == numpy_rng
    effect.close()


def test_snow_collision_surface_stays_fixed_while_floor_moves():
    effect = snow(height=10)
    collision = Buffer(2, 2)
    effect.update_collision(1, 3, 2, 2, True, False, collision)
    effect.ground_flakes[3][2] = 12  # Snow perched above the collision rectangle.
    effect.ground_flakes[2][2] = 4
    effect.ground_flakes[9][2] = 18
    effect.resize((9, 14))
    assert effect.ground_flakes[3][2] == 12
    assert effect.ground_flakes[2][2] == 4
    assert effect.ground_flakes[13][2] == 18
    assert effect.image_buffer is collision
    assert effect.image_x_boundaries == (1, 3)
    assert effect.image_y_boundaries == (3, 5)
    assert effect.is_colliding(2, 4)


def test_snow_shrink_discards_cropped_or_covered_flakes_and_never_resurrects_them():
    effect = snow()
    for x, y in ((0, 0), (4, 0), (1, 5), (2, 1)):
        effect.generate_snowflake(x)
        effect.flakes[-1]["y"] = y
    effect.ground_flakes[5][2] = 18
    effect.ground_flakes[4][2] = 4
    effect.ground_flakes[5][4] = 7

    effect.resize((3, 2))
    assert [(f["x"], f["y"]) for f in effect.flakes] == [(0, 0)]
    assert effect.ground_flakes == [[0, 0, 4], [0, 0, 18]]
    effect.resize((5, 6))
    assert effect.ground_flakes[4][2] == 4
    assert effect.ground_flakes[5][2] == 18
    assert sum(map(sum, effect.ground_flakes)) == 22
    assert [(f["x"], f["y"]) for f in effect.flakes] == [(0, 0)]
    effect.resize((1, 1))
    effect.update(1 / 30)
    assert effect.buffer.width() == effect.buffer.height() == 1


def test_snow_spawns_in_new_columns_and_lands_at_new_floor(monkeypatch):
    effect = snow(width=2, height=2)
    effect.resize((6, 4))
    effect.set_snow_intensity(1)
    effect.update(1 / 30)
    assert {f["x"] for f in effect.flakes} == set(range(6))
    effect.set_snow_intensity(0)
    monkeypatch.setattr(effect.rng, "choices", lambda *a, **k: [0])
    for _ in range(30):
        effect.update(1 / 30)
    assert not effect.flakes
    assert effect.ground_flakes[-1] == [1] * 6
    assert not any(any(row) for row in effect.ground_flakes[:-1])


@pytest.mark.parametrize(
    "kind", [SnowEffect, PlasmaEffect, FireEffect, RainEffect, MatrixEffect]
)
def test_same_size_notification_does_not_repaint_or_consume_randomness(kind):
    effect = kind(Buffer(3, 5), " ")
    effect.update(1 / 30)
    raster = effect.buffer
    cells = deepcopy(raster.buffer)
    rng = effect.rng.getstate()
    effect.resize((5, 3))
    assert effect.buffer is raster and effect.buffer.buffer == cells
    assert effect.rng.getstate() == rng


@pytest.mark.parametrize(
    "kind", [SnowEffect, PlasmaEffect, FireEffect, RainEffect, MatrixEffect]
)
@pytest.mark.parametrize("size", [(0, 3), (-1, 2), (True, 2), (2.5, 3), [2, 3]])
def test_invalid_resize_leaves_simulation_unchanged(kind, size):
    effect = kind(Buffer(3, 5), " ")
    raster = effect.buffer
    with pytest.raises((TypeError, ValueError)):
        effect.resize(size)
    assert effect.buffer is raster and effect._viewport is None


@pytest.mark.parametrize("colored", [False, True])
def test_plasma_repaints_new_dimensions_at_same_phase_and_palette(colored):
    effect = PlasmaEffect(
        Buffer(3, 5), " ", PlasmaSettings(seed=7, color=colored, characters=False)
    )
    for _ in range(6):
        effect.update(1 / 30)
    original = deepcopy(effect.buffer.buffer)
    frame = Buffer(3, 5)
    effect.draw(frame)
    phase, palette, frequencies = effect.t, list(effect.colors), list(effect.vals)
    rng = effect.rng.getstate()
    effect.resize((12, 8))
    reference = PlasmaEffect(
        Buffer(8, 12), " ", PlasmaSettings(seed=7, color=colored, characters=False)
    )
    for _ in range(6):
        reference.update(1 / 30)
    assert effect.buffer.buffer == reference.buffer.buffer
    assert effect.t == phase and effect.colors == palette and effect.vals == frequencies
    assert effect.rng.getstate() == rng
    assert frame.buffer == original
    effect.resize((5, 3))
    assert effect.buffer.buffer == original


def test_fitting_panel_adapts_snow_before_next_scheduled_update():
    effect = snow(width=5, height=3)
    panel = Panel(effect, size=(5, 3), fit=True, updates_per_second=1)
    layout = Column(Slot(panel)).build(Buffer(5, 7))
    layout.start()
    effect.ground_flakes[-1][0] = 18
    effect.update = Mock(side_effect=AssertionError("unexpected tick"))
    layout.resize((12, 8))
    frame = Buffer(8, 12)
    layout.draw(frame)
    assert panel.size == (10, 6)
    assert effect.ground_flakes[5][0] == 18
    assert frame.get_char(1, 6) == "#"
    assert frame.get_char(0, 7) == "+"
    effect.update.assert_not_called()
    layout.close()


def test_dashboard_snow_adapts_while_paused_solver_remains_unchanged():
    playback = Playback(solve(), draw_state, paused=True)
    scene = build_scene(Buffer(24, 80), playback)
    scene.start()
    background = scene.layers[0].animation
    assert isinstance(background, SnowEffect)
    background.ground_flakes[-1][0] = 18
    scene.resize((100, 30))
    target = Buffer(30, 100)
    scene.draw(target)
    assert background.buffer.width() == 100 and background.buffer.height() == 30
    assert target.get_char(0, 29) == "#"
    assert playback.steps == 0 and playback.paused and not playback.has_state
    scene.close()


def test_fire_relocates_both_heat_fields_spots_and_raster_without_random_flicker():
    effect = FireEffect(Buffer(4, 3), " ", FireSettings(seed=42, swell=True))
    effect.previous_data[:] = np.arange(12).reshape(4, 3)
    effect.current_data[:] = effect.previous_data + 20
    effect.buffer.buffer = [list(row) for row in ("abc", "def", "ghi", "jkl")]
    effect.heat_spots = [
        {
            "x": 1.5,
            "y": 3,
            "lifetime": 9,
            "intensity": 0.8,
            "x_offset": 0.1,
            "y_offset": 0.2,
        },
        {
            "x": 2,
            "y": 0,
            "lifetime": 4,
            "intensity": 0.5,
            "x_offset": 0.0,
            "y_offset": 0.0,
        },
    ]
    effect._tick = 17
    effect._update_random_variations_counter = 3
    before = deepcopy(effect.heat_spots)
    old_previous, old_current, old_buffer = (
        effect.previous_data,
        effect.current_data,
        effect.buffer,
    )
    variations = effect._random_variations.copy()
    rng, numpy_rng = effect.rng.getstate(), deepcopy(effect.np_rng.bit_generator.state)
    effect.resize((5, 7))
    np.testing.assert_array_equal(effect.previous_data[-4:, :3], old_previous)
    np.testing.assert_array_equal(effect.current_data[-4:, :3], old_current)
    assert not effect.previous_data[:3].any() and not effect.current_data[:, 3:].any()
    assert effect.buffer.buffer[-4:] == [
        list(row + "  ") for row in ("abc", "def", "ghi", "jkl")
    ]
    assert effect.buffer.buffer[:3] == [[" "] * 5 for _ in range(3)]
    assert effect.heat_spots == [{**spot, "y": spot["y"] + 3} for spot in before]
    assert effect.height_cooling_map.shape == (7, 1)
    np.testing.assert_array_equal(effect._random_variations[:3], variations)
    np.testing.assert_array_equal(effect._random_variations[3:], [1, 1])
    assert effect._tick == 17 and effect._update_random_variations_counter == 3
    assert effect.swell_delta == 0.02 and effect.fire_intensity == 0.2
    assert (
        effect.rng.getstate() == rng and effect.np_rng.bit_generator.state == numpy_rng
    )
    effect.resize((2, 2))
    np.testing.assert_array_equal(effect.previous_data, old_previous[-2:, :2])
    np.testing.assert_array_equal(effect.current_data, old_current[-2:, :2])
    assert effect.buffer.buffer == [list("gh"), list("jk")]
    assert effect.heat_spots == [{**before[0], "y": 1}]
    assert old_buffer.buffer == [list(row) for row in ("abc", "def", "ghi", "jkl")]
    assert not np.shares_memory(old_previous, effect.previous_data)


def test_fire_new_columns_receive_fuel_on_next_tick(monkeypatch):
    effect = FireEffect(Buffer(3, 2), " ", FireSettings(seed=42, intensity=1))
    effect.resize((7, 5))
    assert not effect.current_data[:, 2:].any()
    monkeypatch.setattr(effect, "update_data", lambda tick: None)
    # Supply a deterministic NumPy boundary instead of depending on probabilities.
    effect.np_rng = Mock()
    effect.np_rng.uniform.return_value = np.ones(7)
    effect.np_rng.random.return_value = np.zeros(7)
    effect.update(1 / 30)
    np.testing.assert_array_equal(effect.current_data[-1], np.full(7, 255))


def test_rain_keeps_drops_bolt_age_and_image_splashes_but_moves_floor_splashes():
    effect = RainEffect(Buffer(4, 5), " ", RainSettings(seed=42, collision=True))
    effect.buffer.put_char(1, 1, "|")
    effect.buffer.put_char(2, 2, "v")
    effect.buffer.put_char(3, 3, "v")
    bolt_char = "\x1b[38;5;226m/\x1b[0m"
    effect.buffer.put_char(4, 0, bolt_char)
    effect._bolts = [[[(4, 0, "/"), (4, 1, "|")], 7], [[(0, 3, "|")], 5]]
    effect._tick = 19
    effect.swell_direction = -1
    old_buffer = effect.buffer
    original = deepcopy(old_buffer.buffer)
    rng = effect.rng.getstate()
    effect.resize((8, 7))
    assert effect.buffer.get_char(1, 1) == "|"
    assert effect.buffer.get_char(2, 2) == "v"
    assert effect.buffer.get_char(3, 3) == " " and effect.buffer.get_char(3, 6) == "v"
    assert effect.buffer.get_char(4, 0) == bolt_char
    assert effect._bolts == [[[(4, 0, "/"), (4, 1, "|")], 7], [[(0, 3, "|")], 5]]
    assert effect._tick == 19 and effect.swell_direction == -1
    assert effect.rng.getstate() == rng
    effect.resize((2, 4))
    assert effect._bolts == [[[(0, 3, "|")], 5]]
    effect.resize((1, 1))
    assert not effect._bolts
    effect.resize((5, 4))
    assert effect.buffer.buffer == [[" "] * 5 for _ in range(4)]
    assert old_buffer.buffer == original and original[3][3] == "v"


def test_rain_growth_keeps_collision_mask_safe_and_new_columns_spawn(monkeypatch):
    effect = RainEffect(
        Buffer(3, 3), " ", RainSettings(seed=42, intensity=600, collision=True)
    )
    mask = Buffer(3, 3)
    mask.put_char(1, 2, "#")
    effect.update_collision(1, 1, 2, 2, True, image_buffer=mask)
    effect.update(1 / 30)
    effect.resize((7, 6))
    effect.buffer.clear_buffer()
    effect.buffer.put_char(1, 0, "|")
    monkeypatch.setattr(effect.rng, "randint", lambda low, high: high)
    effect.update(1 / 30)
    assert effect.buffer.get_char(1, 1) == "v"
    assert all(cell != " " for cell in effect.buffer.buffer[0])
    assert effect.image_buffer is mask and (mask.width(), mask.height()) == (3, 3)
    assert effect.img_start_x == effect.img_start_y == 1


def test_rain_resize_preserves_lightning_expiry_and_clips_partial_bolts():
    effect = RainEffect(
        Buffer(4, 4),
        " ",
        RainSettings(seed=42, intensity=0, lightning=True, lightning_chance=0),
    )
    effect._bolts = [[[(0, 0, "|"), (1, 1, "/"), (3, 3, "|")], 2]]
    effect.resize((2, 2))
    assert effect._bolts == [[[(0, 0, "|"), (1, 1, "/")], 2]]
    effect.update(1 / 30)
    assert effect._bolts[0][1] == 1
    effect.update(1 / 30)
    assert not effect._bolts


def test_matrix_preserves_row_state_and_defers_growth_randomness_until_update():
    effect = MatrixEffect(
        Buffer(2, 3),
        " ",
        MatrixSettings(
            seed=42,
            character_halt_range=(2, 4),
            color_halt_range=(3, 5),
            character_randomness_one=0,
            color_randomness=0,
        ),
    )
    effect.set_gradient([34, 40, 46])
    effect.update(1 / 30)
    effect._MatrixEffect__color_ticks[0] = 7
    effect._MatrixEffect__character_ticks[0] = 3
    character_halts = effect._MatrixEffect__character_halts[:]
    color_halts = effect._MatrixEffect__color_halts[:]
    characters = deepcopy(effect._MatrixEffect__buffer_characters)
    original = deepcopy(effect.buffer.buffer)
    rng = effect.rng.getstate()
    effect.resize((6, 4))
    assert effect._tick == 1 and effect.rng.getstate() == rng
    assert effect._MatrixEffect__character_ticks == [3, 0, 0, 0]
    assert effect._MatrixEffect__color_ticks == [7, 0, 0, 0]
    assert effect._MatrixEffect__character_halts[:2] == character_halts
    assert effect._MatrixEffect__color_halts[:2] == color_halts
    assert [row[:3] for row in effect.buffer.buffer[:2]] == original
    assert effect.buffer.buffer[-1] == [" "] * 6
    # Multiple notifications between ticks must retain exactly the surviving work.
    effect.resize((4, 3))
    effect.resize((5, 4))
    assert effect.rng.getstate() == rng
    effect.update(1 / 30)
    assert effect._tick == 2
    assert effect.get_gradient() == [34, 40, 46]
    assert [
        row[:3] for row in effect._MatrixEffect__buffer_characters[:2]
    ] == characters
    assert [row[:3] for row in effect.buffer.buffer[:2]] == original
    assert all(
        char != " " for row in effect._MatrixEffect__buffer_characters for char in row
    )
    assert all(2 <= halt <= 4 for halt in effect._MatrixEffect__character_halts)
    assert all(3 <= halt <= 5 for halt in effect._MatrixEffect__color_halts)
    assert (
        not effect._MatrixEffect__pending_cells
        and not effect._MatrixEffect__pending_rows
    )


@pytest.mark.parametrize(
    "kind, settings",
    [
        (
            FireEffect,
            FireSettings(seed=42, swell=True, turbulence=0.3, heat_spot_intensity=1),
        ),
        (
            RainEffect,
            RainSettings(seed=42, lightning=True, lightning_chance=1, intensity=600),
        ),
        (MatrixEffect, MatrixSettings(seed=42)),
    ],
)
def test_resize_sequences_are_deterministic_safe_before_start_and_in_tiny_views(
    kind, settings
):
    first, second = (kind(Buffer(3, 5), " ", settings) for _ in range(2))
    for size in ((8, 6), (1, 1), (5, 2), (2, 7), (8, 6)):
        for effect in (first, second):
            rng, numpy_rng = (
                effect.rng.getstate(),
                deepcopy(effect.np_rng.bit_generator.state),
            )
            previous = Buffer(effect.buffer.height(), effect.buffer.width())
            effect.draw(previous)
            pixels = deepcopy(previous.buffer)
            effect.resize(size)
            assert (
                effect.rng.getstate() == rng
                and effect.np_rng.bit_generator.state == numpy_rng
            )
            effect.start()
            for _ in range(12):
                effect.update(1 / 30)
            a, b = Buffer(size[1], size[0]), Buffer(size[1], size[0])
            effect.draw(a)
            effect.draw(b)
            assert a.buffer == b.buffer and previous.buffer == pixels
            assert all(len(row) == size[0] for row in effect.buffer.buffer)
        first_frame, second_frame = Buffer(size[1], size[0]), Buffer(size[1], size[0])
        first.draw(first_frame)
        second.draw(second_frame)
        assert first_frame.buffer == second_frame.buffer
        assert first.rng.getstate() == second.rng.getstate()
    first.close()
    second.close()


@pytest.mark.parametrize("name", ["fire", "rain", "matrix"])
def test_new_adapters_run_through_player_with_one_owned_instance(name):
    from test_player import Clock
    from test_resize import ResizingScreen

    screen = ResizingScreen({1: (9, 6), 2: (1, 1), 3: (5, 3)})
    clock = Clock()
    effect = effect_registry.create(name, Buffer(3, 5), " ", seed=42)
    start, close = Mock(wraps=effect.start), Mock(wraps=effect.close)
    effect.start, effect.close = start, close
    assert (
        Player(
            screen, effect, frames=4, on_resize="resize", clock=clock, sleep=clock.sleep
        ).run()
        == 4
    )
    start.assert_called_once()
    close.assert_called_once()
    assert effect._tick == 4
