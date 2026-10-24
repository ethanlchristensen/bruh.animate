from unittest.mock import Mock

import pytest

from bruhanimate import AnimationSequence, Buffer, CallbackEffect, SequenceStep


class Child:
    def __init__(self, calls, name, fail=None):
        self.calls, self.name, self.fail = calls, name, fail
        self.elapsed = 0
        self.finished = False

    def start(self):
        self.calls.append((self.name, "start"))
        if self.fail == "start":
            raise RuntimeError("start failed")

    def update(self, dt):
        self.elapsed += dt
        self.calls.append((self.name, "update", dt))

    def draw(self, buffer):
        buffer.put_char(0, 0, self.name)

    def resize(self, size):
        self.calls.append((self.name, "resize", size))
        if self.fail == "resize":
            raise RuntimeError("resize failed")

    def close(self):
        self.calls.append((self.name, "close"))
        if self.fail == "close":
            raise RuntimeError("close failed")


def frame(sequence):
    buffer = Buffer(1, 1).clear_buffer(val=None)
    sequence.draw(buffer)
    return buffer.get_char(0, 0)


def test_factory_laziness_holds_gaps_resize_and_completion():
    calls = []
    a = Mock(side_effect=lambda: Child(calls, "A"))
    b = Mock(side_effect=lambda: Child(calls, "B"))
    sequence = AnimationSequence(
        SequenceStep(a, 2, hold_duration=1, gap=1, name="one"),
        SequenceStep(b, 3, name="two"),
    )
    assert sequence.current is None and sequence.duration == 7
    sequence.resize((1, 1))
    a.assert_not_called()
    assert frame(sequence) is None
    sequence.start()
    sequence.start()
    assert calls == [("A", "start"), ("A", "resize", (1, 1))]
    sequence.update(2.5)
    assert sequence.current.elapsed == 2
    assert frame(sequence) == "A" and not sequence.finished
    sequence.update(0.5)
    assert frame(sequence) is None and not sequence.visible
    sequence.update(1.5)
    assert sequence.phase_name == "two" and sequence.index == 1
    assert calls[-4:] == [
        ("A", "close"),
        ("B", "start"),
        ("B", "resize", (1, 1)),
        ("B", "update", 0.5),
    ]
    sequence.update(100)
    assert sequence.finished and sequence.current.elapsed == 3
    assert frame(sequence) == "B"
    before = calls.copy()
    sequence.update(3)
    assert calls == before
    sequence.close()
    sequence.close()
    assert calls[-1] == ("B", "close") and sequence.current is None


def test_large_jumps_skip_factories_and_repeat_creates_fresh_child():
    calls = []
    factories = [
        Mock(side_effect=lambda name=name: Child(calls, name)) for name in "ABC"
    ]
    sequence = AnimationSequence(
        *(SequenceStep(f, 1, name=n) for f, n in zip(factories, "ABC")), repeat=True
    )
    sequence.start()
    first = sequence.current
    sequence.update(3_000_002.5)
    assert sequence.index == 2 and sequence.current.elapsed == 0.5
    factories[1].assert_not_called()
    assert factories[0].call_count == 1 and factories[2].call_count == 1
    sequence.update(0.5)
    assert sequence.index == 0 and sequence.current is not first
    assert not sequence.finished
    sequence.close()


def test_finished_child_freezes_but_does_not_change_step_timing():
    child = Child([], "A")
    sequence = AnimationSequence(SequenceStep(lambda: child, 2, gap=1))
    sequence.start()
    sequence.update(0.5)
    child.finished = True
    sequence.update(1)
    assert child.elapsed == 0.5 and not sequence.finished
    assert frame(sequence) == "A"
    sequence.update(10)
    assert sequence.finished and frame(sequence) is None
    sequence.close()


@pytest.mark.parametrize("failure", ["start", "resize"])
def test_partial_start_failure_closes_once(failure):
    calls = []
    sequence = AnimationSequence(SequenceStep(lambda: Child(calls, "A", failure), 1))
    sequence.resize((3, 2))
    with pytest.raises(RuntimeError, match=failure):
        sequence.start()
    sequence.close()
    assert calls.count(("A", "close")) == 1
    assert sequence.current is None


def test_close_failure_does_not_start_next_child_or_close_again():
    calls = []
    factory = Mock()
    sequence = AnimationSequence(
        SequenceStep(lambda: Child(calls, "A", "close"), 1), SequenceStep(factory, 1)
    )
    sequence.start()
    with pytest.raises(RuntimeError, match="close"):
        sequence.update(1)
    sequence.close()
    factory.assert_not_called()
    assert calls.count(("A", "close")) == 1


def test_empty_and_close_before_start_are_inert():
    empty = AnimationSequence(repeat=True)
    assert empty.finished and empty.duration == 0
    empty.start()
    empty.update(1)
    empty.close()
    factory = Mock()
    sequence = AnimationSequence(SequenceStep(factory, 1))
    sequence.close()
    sequence.close()
    factory.assert_not_called()
    with pytest.raises(RuntimeError, match="closed"):
        sequence.start()


def test_invalid_factory_return_and_exception_leave_closed_sequence():
    for factory in (lambda: object(), Mock(side_effect=RuntimeError("factory failed"))):
        sequence = AnimationSequence(SequenceStep(factory, 1))
        with pytest.raises((RuntimeError, TypeError)):
            sequence.start()
        sequence.close()
        assert sequence.current is None


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"duration": 0}, ValueError),
        ({"duration": -1}, ValueError),
        ({"duration": float("inf")}, ValueError),
        ({"duration": True}, TypeError),
        ({"hold_duration": -1}, ValueError),
        ({"gap": float("nan")}, ValueError),
        ({"name": 3}, TypeError),
        ({"factory": None}, TypeError),
        ({"duration": 1e308, "hold_duration": 1e308}, ValueError),
    ],
)
def test_step_validation(kwargs, error):
    options = {"factory": lambda: CallbackEffect(lambda b: None), "duration": 1}
    options.update(kwargs)
    with pytest.raises(error):
        SequenceStep(**options)


def test_sequence_validation_and_draw_purity():
    with pytest.raises(TypeError):
        AnimationSequence("invalid")
    with pytest.raises(TypeError):
        AnimationSequence(repeat=1)
    calls = []
    sequence = AnimationSequence(SequenceStep(lambda: Child(calls, "A"), 0.1))
    with pytest.raises(RuntimeError):
        sequence.update(0.1)
    sequence.start()
    for _ in range(6):
        sequence.update(1 / 60)
    assert sequence.finished
    before = calls.copy()
    assert frame(sequence) == frame(sequence)
    assert calls == before
    with pytest.raises(ValueError):
        sequence.update(-1)
    sequence.close()


def test_fractional_ticks_replace_child_on_single_step_repeat():
    calls = []
    sequence = AnimationSequence(
        SequenceStep(lambda: Child(calls, "A"), 0.1), repeat=True
    )
    sequence.start()
    original = sequence.current
    for _ in range(6):
        sequence.update(1 / 60)
    assert sequence.current is not original
    assert calls.count(("A", "close")) == 1
    sequence.update(1 / 60)
    assert sequence.current.elapsed == pytest.approx(1 / 60)
    sequence.close()


def test_fractional_ticks_hit_internal_step_and_gap_boundaries():
    calls = []
    sequence = AnimationSequence(
        SequenceStep(lambda: Child(calls, "A"), 0.1, gap=0.1),
        SequenceStep(lambda: Child(calls, "B"), 0.1),
    )
    sequence.start()
    for _ in range(6):
        sequence.update(1 / 60)
    assert not sequence.visible
    for _ in range(6):
        sequence.update(1 / 60)
    assert sequence.index == 1 and sequence.current.elapsed == 0
    sequence.close()
