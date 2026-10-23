from bruhanimate.bruheffect.static_effect import StaticEffect
from bruhanimate.bruhutil.bruhffer import Buffer


def test_static_effect_render():
    buffer = Buffer(5, 10)
    effect = StaticEffect(buffer, "x")

    # Should fill the buffer with 'x'
    effect.update(1 / 30)

    for y in range(5):
        for x in range(10):
            assert effect.buffer.get_char(x, y) == "x"


def test_static_effect_render_multi_char():
    buffer = Buffer(5, 10)
    effect = StaticEffect(buffer, "xy")

    # Should fill the buffer with 'xy' repeating
    effect.update(1 / 30)

    for y in range(5):
        assert "".join(effect.buffer.grab_slice(0, y, 10)) == "xyxyxyxyxy"
