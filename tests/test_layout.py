import pytest

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Column,
    Fixed,
    Flex,
    ImageEffect,
    Label,
    Panel,
    Row,
    Scene,
    Slot,
    Spacer,
    TimedOverlay,
    capture,
)


class Probe:
    def __init__(self, name="x", events=None, fail=False):
        self.name, self.events, self.fail = (
            name,
            events if events is not None else [],
            fail,
        )
        self.updates = []

    def start(self):
        self.events.append(f"start {self.name}")
        if self.fail:
            raise RuntimeError("startup failed")

    def update(self, dt):
        self.updates.append(dt)

    def draw(self, buffer):
        buffer.clear_buffer(val=self.name)

    def close(self):
        self.events.append(f"close {self.name}")


def test_row_reserves_fixed_cells_and_uses_weighted_largest_remainders():
    row = Row(Spacer(Flex(1)), Spacer(Fixed(3)), Spacer(Flex(2)), gap=1, padding=1)
    assert row.regions((18, 6)) == ((1, 1, 4, 4), (6, 1, 3, 4), (10, 1, 7, 4))
    assert Row(Spacer(), Spacer()).regions((5, 2)) == ((0, 0, 3, 2), (3, 0, 2, 2))


def test_column_transposes_axes_and_fixed_shortage_is_declaration_order():
    column = Column(Spacer(Fixed(4)), Spacer(Fixed(4)), Spacer(), gap=1)
    assert column.regions((3, 8)) == ((0, 0, 3, 4), (0, 5, 3, 2), (0, 8, 3, 0))
    assert Column(Spacer(), padding=5).regions((3, 2)) == ((5, 5, 0, 0),)
    assert Row().regions((0, 0)) == ()


def test_nested_layouts_allocate_local_buffers_and_preserve_gaps():
    sizes = []

    def factory(buffer):
        sizes.append((buffer.width(), buffer.height()))
        return CallbackEffect(lambda target: target.clear_buffer(val="x"))

    layout = Column(
        Slot(Label("HEAD"), size=Fixed(1)),
        Slot(
            Row(
                Slot(effect_factory=factory),
                Spacer(Fixed(1)),
                Slot(Label("R"), size=Fixed(2)),
            )
        ),
        padding=1,
        gap=1,
    )
    animation = layout.build(Buffer(6, 10))
    assert sizes == []
    animation.start()
    try:
        target = Buffer(6, 10).clear_buffer(val=".")
        animation.draw(target)
        assert sizes == [(5, 2)]
        assert target.buffer == [
            list(row)
            for row in (
                "..........",
                ".HEAD    .",
                "..........",
                ".xxxxx.R .",
                ".xxxxx.  .",
                "..........",
            )
        ]
        second = Buffer(6, 10).clear_buffer(val=".")
        animation.draw(second)
        assert target.buffer == second.buffer
    finally:
        animation.close()


def test_factory_binding_is_lazy_and_each_effect_keeps_its_own_surface():
    seen = []

    def factory(buffer):
        seen.append(buffer)
        return Panel(
            ImageEffect("ok"), size=(buffer.width(), buffer.height()), border=False
        )

    layout = Row(Slot(effect_factory=factory), Slot(effect_factory=factory))
    animation = layout.build(Buffer(3, 8))
    assert seen == []
    animation.start()
    animation.start()
    try:
        assert len(seen) == 2 and seen[0] is not seen[1]
        assert all((buf.width(), buf.height()) == (4, 3) for buf in seen)
    finally:
        animation.close()
    with pytest.raises(RuntimeError, match="single-use"):
        layout.build(Buffer(3, 8))
    with pytest.raises(RuntimeError, match="single-use"):
        animation.start()


def test_zero_area_slots_skip_factories_and_close_hidden_supplied_children():
    events, factories = [], []
    hidden = Probe("h", events)
    nested = Column(
        Slot(hidden), Slot(effect_factory=lambda buffer: factories.append(buffer))
    )
    animation = Row(
        Slot(nested), Slot(effect_factory=lambda buffer: factories.append(buffer))
    ).build(Buffer(0, 5))
    animation.start()
    animation.update(10)
    animation.draw(Buffer(0, 5))
    assert events == [] and factories == [] and animation.finished is None
    animation.close()
    animation.close()
    assert events == ["close h"]


def test_close_before_start_disposes_nested_content_without_acquiring_factories():
    events = []
    layout = Row(
        Slot(Probe("a", events)),
        Slot(Column(Slot(Probe("b", events)))),
        Slot(effect_factory=lambda buffer: pytest.fail("factory called")),
    )
    animation = layout.build(Buffer(4, 12))
    animation.close()
    animation.close()
    assert events == ["close b", "close a"]


def test_partial_start_failure_closes_started_and_unstarted_owned_content_once():
    events = []
    animation = Row(
        *(Slot(Probe(name, events, fail=name == "b")) for name in "abc")
    ).build(Buffer(2, 9))
    with pytest.raises(RuntimeError, match="startup failed"):
        animation.start()
    animation.close()
    assert events == ["start a", "start b", "close b", "close a", "close c"]


def test_cleanup_continues_if_a_child_close_raises():
    events = []
    a, b = Probe("a", events), Probe("b", events)

    def fail_close():
        events.append("close b")
        raise RuntimeError("close failed")

    b.close = fail_close
    animation = Row(Slot(a), Slot(b)).build(Buffer(2, 8))
    animation.start()
    with pytest.raises(RuntimeError, match="close failed"):
        animation.close()
    assert events[-2:] == ["close b", "close a"]
    animation.close()


def test_repeated_child_ownership_is_rejected_across_nested_layouts():
    child = Label("shared")
    with pytest.raises(ValueError, match="same animation"):
        Row(Slot(child), Slot(Column(Slot(child)))).build(Buffer(4, 20))
    nested = Column(Slot(Label("nested")))
    with pytest.raises(ValueError, match="same child"):
        Row(Slot(nested), Slot(nested)).build(Buffer(4, 20))


def test_parent_reserves_nested_layout_against_separate_builds():
    nested = Column(Slot(Label("x")))
    animation = Row(Slot(nested)).build(Buffer(3, 4))
    with pytest.raises(RuntimeError, match="single-use"):
        nested.build(Buffer(3, 4))
    animation.close()


def test_background_spaces_and_transparency_follow_scene_rules():
    def make(background):
        return Row(
            Slot(Label(" "), size=Fixed(1)), Spacer(), background=background
        ).build(Buffer(1, 3))

    for background, expected in [(None, " .."), ("x", " xx")]:
        frames = []
        capture(
            Scene(ImageEffect("..."), make(background)),
            width=3,
            height=1,
            frames=1,
            on_frame=frames.append,
        )
        assert frames[0].text() == expected


def test_finite_child_completion_propagates_through_nested_layouts():
    child = TimedOverlay(Label("x"), duration=0.1)
    layout = Column(Slot(Row(Slot(child))), Slot(Label("endless"), size=Fixed(1)))
    animation = layout.build(Buffer(3, 8))
    assert (
        capture(
            animation, width=8, height=3, fps=30, frames=60, on_frame=lambda frame: None
        )
        < 60
    )
    assert animation.finished is True


def test_drawing_does_not_update_or_evaluate_text_and_old_frames_stay_unchanged():
    calls = []
    label = Label(lambda: str(len(calls.append(None) or calls)))
    animation = Column(Slot(label)).build(Buffer(1, 3))
    animation.start()
    first, repeat = Buffer(1, 3), Buffer(1, 3)
    animation.draw(first)
    animation.draw(repeat)
    assert calls == [None] and first.buffer == repeat.buffer == [list("1  ")]
    animation.update(0.1)
    animation.draw(repeat)
    assert repeat.buffer == [list("2  ")] and first.buffer == [list("1  ")]
    animation.close()


def test_invalid_factory_return_and_dimensions_cleanup_through_player():
    with pytest.raises(TypeError, match="Animation"):
        capture(
            effect_factory=Row(Slot(effect_factory=lambda buffer: "bad")).build,
            width=3,
            height=2,
            frames=2,
            on_frame=lambda frame: None,
        )
    animation = Row(Slot(Label("x"))).build(Buffer(2, 3))
    with pytest.raises(RuntimeError, match="started"):
        animation.draw(Buffer(2, 3))
    animation.start()
    try:
        with pytest.raises(ValueError, match="bound dimensions"):
            animation.draw(Buffer(2, 4))
        with pytest.raises(ValueError):
            animation.update(-1)
    finally:
        animation.close()


@pytest.mark.parametrize(
    "factory, error",
    [
        (lambda: Fixed(-1), ValueError),
        (lambda: Fixed(True), TypeError),
        (lambda: Flex(0), ValueError),
        (lambda: Flex(1.5), TypeError),
        (lambda: Row(gap=-1), ValueError),
        (lambda: Column(padding=True), TypeError),
        (lambda: Row(Label("x")), TypeError),
        (lambda: Spacer(1), TypeError),
        (lambda: Slot(), ValueError),
        (lambda: Slot("x"), TypeError),
        (
            lambda: Slot(Label("x"), effect_factory=lambda buffer: Label("y")),
            ValueError,
        ),
        (lambda: Slot(Label("x"), size=3), TypeError),
        (lambda: Slot(effect_factory=42), TypeError),
        (lambda: Row(background="wide"), ValueError),
        (lambda: Row().regions((2, -1)), ValueError),
        (lambda: Row().regions([2, 3]), TypeError),
    ],
)
def test_invalid_layout_settings_fail_early(factory, error):
    with pytest.raises(error):
        factory()
