"""Compare optimized plasma to the scalar visual specification."""

import math

import pytest

from bruhanimate import Buffer, PlasmaEffect, PlasmaSettings


def scalar_frame(effect):
    width, height = effect.buffer.width(), effect.buffer.height()
    result = Buffer(height, width)
    phase = effect.t / 3.0

    def wave(x, y, a, b, frequency):
        return math.sin(
            math.sqrt((x - width * a) ** 2 + 4 * (y - height * b) ** 2)
            * math.pi
            / frequency
        )

    for y in range(height):
        for x in range(width):
            value = (
                abs(
                    wave(x + phase, y, 1 / 4, 1 / 3, effect.vals[0])
                    + wave(x, y, 1 / 8, 1 / 5, effect.vals[1])
                    + wave(x, y + phase, 1 / 2, 1 / 5, effect.vals[2])
                    + wave(x, y, 3 / 4, 4 / 5, effect.vals[3])
                )
                / 4.0
            )
            result.put_char(
                x, y, effect._colored_cache[int((len(effect.scale) - 1) * value)]
            )
    return result.buffer


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize(
    "color,characters", [(False, True), (True, True), (True, False)]
)
def test_plasma_scalar_parity_after_ticks_settings_and_resize(seed, color, characters):
    effect = PlasmaEffect(
        Buffer(9, 23),
        " ",
        PlasmaSettings(seed=seed, color=color, characters=characters),
    )
    try:
        for phase in (0, 1, 17, 300, 10000):
            effect.t = phase
            effect.update(1 / 30)
            assert effect.buffer.buffer == scalar_frame(effect)
        for action in (
            lambda: effect.set_plasma_values(1, 2, 3, 4),
            effect.shuffle_plasma_values,
            lambda: effect.vals.__setitem__(1, 13),
            lambda: effect.set_grey_scale_size(16),
            lambda: effect.set_color_properties(True, False),
            lambda: effect.set_colors(list(range(len(effect.scale)))),
        ):
            action()
            effect.update(1 / 30)
            assert effect.buffer.buffer == scalar_frame(effect)
        for size in ((1, 1), (32, 16), (4, 3), (23, 9)):
            phase, rng = effect.t, effect.rng.getstate()
            effect.resize(size)
            assert effect.buffer.buffer == scalar_frame(effect)
            assert effect.t == phase and effect.rng.getstate() == rng
            first, second = Buffer(size[1], size[0]), Buffer(size[1], size[0])
            effect.draw(first)
            effect.draw(second)
            assert first.buffer == second.buffer == scalar_frame(effect)
    finally:
        effect.close()


def test_plasma_zero_phase_at_wave_centers_matches_scalar_boundaries():
    effect = PlasmaEffect(Buffer(15, 40), " ", PlasmaSettings(seed=9))
    try:
        effect.set_plasma_values(1, 1, 1, 1)
        effect.resize((80, 30))
        assert effect.buffer.buffer == scalar_frame(effect)
    finally:
        effect.close()
