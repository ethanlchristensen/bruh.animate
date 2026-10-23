from bruhanimate.bruheffect.base_effect import BaseEffect
from bruhanimate.bruhutil.bruhffer import Buffer


class DummyEffect(BaseEffect):
    def update(self, dt):
        pass


def test_base_effect_init():
    """Test initialization of the base effect class."""
    buffer = Buffer(10, 20)
    effect = DummyEffect(buffer, "*")

    assert effect.buffer == buffer
    assert effect.background == "*"
    assert effect.background_length == 1
