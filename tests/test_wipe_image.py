import pytest

from bruhanimate import Buffer, WipeImageEffect


def render(effect, size=(4, 2)):
    buffer = Buffer(size[1], size[0]).clear_buffer(val=None)
    effect.draw(buffer)
    return buffer.buffer


@pytest.mark.parametrize(
    "direction,expected",
    [
        ("right", [["A", "B", None, None], ["E", "F", None, None]]),
        ("left", [[None, None, "C", "D"], [None, None, "G", "H"]]),
        ("down", [list("ABCD"), [None] * 4]),
        ("up", [[None] * 4, list("EFGH")]),
    ],
)
def test_direction_and_exact_reverse_frames(direction, expected):
    effect = WipeImageEffect(
        ["ABCD", "EFGH"], duration=2, direction=direction, reverse=True, hold_duration=1
    )
    initial = render(effect)
    assert initial == [[None] * 4] * 2
    effect.update(1)
    assert render(effect) == expected
    effect.update(1.5)
    assert render(effect) == [list("ABCD"), list("EFGH")]
    effect.update(1.5)
    assert render(effect) == expected
    assert render(effect) == expected
    effect.update(1)
    assert effect.finished and render(effect) == initial


def test_spaces_ragged_rows_center_resize_and_repeats():
    effect = WipeImageEffect(
        ["A B", "C"],
        duration=1,
        repeat=True,
        reverse=True,
        hold_duration=0,
        repeat_delay=1,
    )
    effect.update(30001)
    before = render(effect, (5, 4))
    assert before[1][1:4] == ["A", None, "B"]
    assert before[2][1] == "C"
    render(effect, (1, 1))
    assert render(effect, (5, 4)) == before
    effect.update(1)
    assert render(effect) == [[None] * 4] * 2
    assert not effect.finished
    assert WipeImageEffect([], repeat=True).finished


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"direction": "in"}, ValueError),
        ({"duration": 0}, ValueError),
        ({"duration": True}, TypeError),
        ({"duration": float("inf")}, ValueError),
        ({"repeat": 1}, TypeError),
        ({"reverse": "yes"}, TypeError),
        ({"repeat_delay": -1}, ValueError),
    ],
)
def test_validation(kwargs, error):
    with pytest.raises(error):
        WipeImageEffect("A", **kwargs)
