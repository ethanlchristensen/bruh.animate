"""Resize simulations using inert effects and synthetic audio, never real devices."""

from copy import deepcopy
from typing import get_args
from unittest.mock import Mock

import numpy as np
import pytest

from bruhanimate import (
    AudioEffect,
    AudioSettings,
    Buffer,
    TerminalEffect,
    effect_registry,
)
from bruhanimate.bruheffect.settings import AudioMode


@pytest.mark.parametrize("name", effect_registry.names())
def test_every_builtin_grows_shrinks_and_keeps_rng_without_ticking(name, monkeypatch):
    effect = effect_registry.create(name, Buffer(8, 16), " ")
    # Audio stays unstarted: zero-filled synthetic capture, no hardware.
    effect.update(1 / 30)
    update = effect.update
    monkeypatch.setattr(
        effect, "update", Mock(side_effect=AssertionError("resize must not tick"))
    )
    try:
        for width, height in ((24, 12), (24, 12), (1, 1), (20, 10)):
            py_state, np_state = (
                effect.rng.getstate(),
                deepcopy(effect.np_rng.bit_generator.state),
            )
            effect.resize((width, height))
            assert effect.rng.getstate() == py_state
            assert effect.np_rng.bit_generator.state == np_state
            assert (effect.buffer.width(), effect.buffer.height()) == (width, height)
            first, second = Buffer(height, width), Buffer(height, width)
            effect.draw(first)
            effect.draw(second)
            assert first.buffer == second.buffer
            update(1 / 30)
            assert all(len(row) == width for row in effect.buffer.buffer)
        with pytest.raises(ValueError):
            effect.resize((0, 5))
        assert (effect.buffer.width(), effect.buffer.height()) == (20, 10)
    finally:
        effect.close()


def test_grid_state_anchors_and_new_cells():
    diffusion = effect_registry.create("diffusion", Buffer(4, 6), " ")
    u, v = diffusion._U.copy(), diffusion._V.copy()
    diffusion.resize((8, 7))
    np.testing.assert_array_equal(diffusion._U[:4, :6], u)
    np.testing.assert_array_equal(diffusion._V[:4, :6], v)
    assert np.all(diffusion._U[4:] == 1) and np.all(diffusion._V[4:] == 0)
    sand = effect_registry.create("sand", Buffer(4, 6), " ")
    sand._grid[2, 2] = 1
    sand.resize((8, 7))
    assert sand._grid[5, 2] == 1 and sand._grid.sum() == 1
    sand.resize((3, 3))
    assert sand._grid[1, 2] == 1
    gol = effect_registry.create("gol", Buffer(4, 6), " ")
    gol.update(0.1)
    board, tick = deepcopy(gol.board), gol._tick
    gol.resize((8, 7))
    assert gol._tick == tick
    assert [[c[1] for c in row[:6]] for row in gol.board[:4]] == [
        [c[1] for c in row] for row in board
    ]
    assert all(cell[1] == 0 for row in gol.board[4:] for cell in row)
    automaton = effect_registry.create("automaton", Buffer(4, 6), " ")
    automaton.update(0.1)
    row = automaton._row.copy()
    automaton.resize((8, 7))
    np.testing.assert_array_equal(automaton._row[:6], row)
    assert not automaton._row[6:].any()


def test_particles_and_fields_preserve_velocity_and_phase():
    boids = effect_registry.create("boids", Buffer(8, 16), " ")
    positions, velocities = boids._pos.copy(), boids._vel.copy()
    boids.resize((4, 3))
    np.testing.assert_array_equal(boids._vel, velocities)
    np.testing.assert_array_equal(boids._pos, positions % [4, 3])
    voronoi = effect_registry.create("voronoi", Buffer(8, 16), " ")
    velocities = voronoi._seeds[:, 2:].copy()
    voronoi.resize((4, 3))
    np.testing.assert_array_equal(voronoi._seeds[:, 2:], velocities)
    assert voronoi._X.shape == (3, 4)
    perlin = effect_registry.create("perlin", Buffer(8, 16), " ")
    perlin.update(0.1)
    phase, offsets = perlin._t, perlin._offsets.copy()
    perlin.resize((4, 3))
    assert perlin._t == phase and perlin._xs.shape == (3, 4)
    np.testing.assert_array_equal(perlin._offsets, offsets)


def test_twinkle_new_cells_seed_only_on_update():
    from bruhanimate import TwinkleEffect, TwinkleSettings

    effect = TwinkleEffect(Buffer(2, 2), " ", TwinkleSettings(density=1, seed=7))
    before = [
        (effect.buffer.get_char(x, y).value, effect.buffer.get_char(x, y).mode)
        for x, y in effect.specs
    ]
    effect.resize((4, 3))
    assert len(effect.specs) == 4
    assert before == [
        (effect.buffer.get_char(x, y).value, effect.buffer.get_char(x, y).mode)
        for x, y in effect.specs
    ]
    effect.resize((3, 3))
    effect.update(0.1)
    assert len(set(effect.specs)) == 9


@pytest.mark.parametrize("mode", get_args(AudioMode))
def test_audio_modes_resize_with_synthetic_signal_without_restarting(mode, monkeypatch):
    effect = AudioEffect(Buffer(8, 16), " ", AudioSettings(mode=mode, seed=42))
    effect._audio_chunk[:] = np.sin(np.arange(len(effect._audio_chunk)) * 0.1)
    effect.update(0.1)
    sample = effect._audio_chunk.copy()
    monkeypatch.setattr(
        effect, "start", Mock(side_effect=AssertionError("must not restart"))
    )
    for size in ((1, 1), (24, 12)):
        effect.resize(size)
        np.testing.assert_array_equal(effect._audio_chunk, sample)
        assert effect._thread is None
        effect.update(0.1)


def test_audio_preserves_latest_wave_history_and_explicit_bar_count():
    effect = AudioEffect(Buffer(8, 6), " ", AudioSettings(num_bars=3))
    effect._wave_history[:] = range(6)
    effect._bars[:] = [0.1, 0.3, 0.5]
    effect.resize((4, 3))
    np.testing.assert_array_equal(effect._wave_history, [2, 3, 4, 5])
    np.testing.assert_array_equal(effect._bars, [0.1, 0.3, 0.5])
    effect.resize((8, 6))
    np.testing.assert_array_equal(effect._wave_history, [0, 0, 0, 0, 2, 3, 4, 5])


def test_terminal_resize_preserves_process_queue_history_and_input():
    effect = TerminalEffect(Buffer(8, 16))
    effect.active_process = Mock()
    process = effect.active_process
    effect.terminal_history[:] = ["first", "second"]
    effect.current_input = "hello"
    effect.output_queue.put("x")
    for size in ((1, 1), (24, 12)):
        effect.resize(size)
        assert effect.active_process is process
        assert effect.output_queue.qsize() == 1
        assert effect.terminal_history == ["first", "second"]
        assert effect.current_input == "hello"
    assert effect.width == 24 and effect.max_lines == 10
    process.terminate.assert_not_called()
    effect.active_process = None
    effect.close()


def test_firework_resize_preserves_life_and_updates_live_bounds():
    from bruhanimate import FireworkEffect, FireworkSettings

    effect = FireworkEffect(Buffer(12, 20), " ", FireworkSettings(rate=1, seed=42))
    for _ in range(4):
        effect.update(0.1)
    particles = [p for f in effect.fireworks for p in f.particles]
    assert particles
    states = [(p.x, p.y, p.life) for p in particles]
    effect.resize((3, 2))
    assert [(p.x, p.y, p.life) for p in particles] == states
    assert all((p.width, p.height) == (3, 2) for p in particles)
    effect.update(0.1)


def test_voronoi_same_size_does_not_snap_valid_subcell_positions():
    effect = effect_registry.create("voronoi", Buffer(4, 8), " ")
    effect._seeds[0, :2] = [7.9, 3.9]
    before = effect._seeds.copy()
    effect.resize((8, 4))
    np.testing.assert_array_equal(effect._seeds, before)
