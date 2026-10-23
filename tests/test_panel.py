import re

import pytest

from bruhanimate import (
    BaseEffect,
    Buffer,
    CallbackEffect,
    ImageEffect,
    Layer,
    Panel,
    Scene,
    TimedOverlay,
    capture,
)


def plain(buffer):
    return [
        [re.sub(r"\x1b\[[0-9;]*m", "", str(cell)) for cell in row]
        for row in buffer.buffer
    ]


class Marker(BaseEffect):
    def __init__(self, glyph="x"):
        super().__init__(Buffer(2, 6), " ")
        self.buffer.clear_buffer(val=glyph)
        self.ticks = []
        self.closes = 0

    def update(self, dt):
        self.ticks.append(dt)

    def close(self):
        self.closes += 1
        super().close()


def window(effect, *, position=(0, 0), velocity=(5, 2), rate=15):
    return Panel(
        effect,
        title="TEST",
        size=(6, 2),
        bounds=(0, 1, 30, 10),
        bounce=True,
        position=(position[0], position[1] + 1),
        velocity=velocity,
        border_color=120,
        updates_per_second=rate,
    )


def test_movement_carries_content_and_reveals_desktop_without_trails():
    effect = Marker()
    moving = window(effect)
    scene = Scene(ImageEffect(["." * 30] * 12, x=0, y=0), moving)
    scene.start()
    try:
        before = Buffer(12, 30)
        scene.draw(before)
        original = [row[:] for row in before.buffer]
        scene.update(1)
        after, repeated = Buffer(12, 30), Buffer(12, 30)
        scene.draw(after)
        scene.draw(repeated)
        assert before.buffer == original
        assert after.buffer == repeated.buffer
        assert moving.position == (5, 3)
        assert plain(after)[1][0] == "."
        assert plain(after)[4][6] == "x"
        assert plain(after)[3][5] == "+"
    finally:
        scene.close()
        scene.close()
    assert effect.closes == 1


def test_front_window_spaces_are_opaque_and_effects_do_not_escape_borders():
    rear = window(Marker("x"), velocity=(0, 0))
    front = window(Marker(" "), position=(2, 1), velocity=(0, 0))
    scene = Scene(rear, front)
    scene.start()
    try:
        result = Buffer(12, 30)
        scene.draw(result)
        cells = plain(result)
        assert cells[2][1] == "x"  # Exposed part of the lower window.
        assert cells[3][3] == " "  # Covered by an opaque upper-window space.
        assert cells[2][2] == "+"
        assert cells[3][2] == "|"
        assert cells[6][3] == " "  # Nothing painted beyond the lower border.
    finally:
        scene.close()


@pytest.mark.parametrize("fps", [30, 60, 120])
def test_bouncing_motion_and_effect_rate_are_independent_of_presentation(fps):
    effect = Marker()
    moving = window(effect)
    moving.start()
    try:
        for _ in range(10 * fps):
            moving.update(1 / fps)
            x, y = moving.position
            assert 0 <= x <= 22 and 1 <= y <= 7
        # Multiple reflections: 50 columns over a 22-column range, 20 rows over 6.
        assert moving.position == pytest.approx((6, 5))
        assert effect.ticks == [1 / 15] * 150
    finally:
        moving.close()


def test_partial_start_failure_closes_each_acquired_effect_once(monkeypatch):
    first, failing = Marker(), Marker()
    order = []
    monkeypatch.setattr(first, "close", lambda: order.append("first"))
    monkeypatch.setattr(failing, "close", lambda: order.append("failing"))

    def fail():
        raise RuntimeError("startup failed")

    monkeypatch.setattr(failing, "start", fail)
    scene = Scene(window(first), window(failing))
    with pytest.raises(RuntimeError, match="startup failed"):
        scene.start()
    scene.close()
    assert order == ["failing", "first"]


def test_factory_is_lazy_and_gets_a_private_content_sized_buffer():
    acquired = []

    class Paint(BaseEffect):
        def update(self, dt):
            self.buffer.put_at(0, 0, "abc")

    def factory(buffer):
        acquired.append(buffer)
        return Paint(buffer, " ")

    panel = Panel(effect_factory=factory, size=(3, 2), position=(2, 1), title="Local")
    assert not acquired and panel.animation is None and panel.finished is None
    panel.start()
    panel.start()
    try:
        assert len(acquired) == 1
        assert (acquired[0].width(), acquired[0].height()) == (3, 2)
        assert panel.size == (3, 2) and panel.outer_size == (5, 4)
        panel.update(1)
        first, second = Buffer(8, 10), Buffer(8, 10)
        panel.draw(first)
        panel.draw(second)
        assert first.buffer == second.buffer
        assert plain(first)[2][3:6] == list("abc")
        assert acquired[0].buffer[0] == list("abc")
    finally:
        panel.close()
    assert not panel.animation._started


def test_nested_panels_use_local_coordinates_and_bounds():
    inner = Panel(
        ImageEffect("abc", x=0, y=0), size=(3, 1), position=(-1, 1), border=False
    )
    outer = Panel(inner, size=(4, 3), position=(2, 1), border=False)
    outer.start()
    try:
        target = Buffer(6, 8).clear_buffer(val=".")
        outer.draw(target)
        assert plain(target)[2] == list("..bc  ..")
        assert inner.position == (-1.0, 1.0)
    finally:
        outer.close()


@pytest.mark.parametrize(
    "background, expected", [(None, ". ."), ("x", "x x"), (" ", "   ")]
)
def test_none_reveals_panel_background_but_child_spaces_paint(background, expected):
    def child(buffer):
        buffer.put_char(1, 0, " ")

    panel = Panel(
        CallbackEffect(child), size=(3, 1), border=False, background=background
    )
    panel.start()
    try:
        target = Buffer(1, 3).clear_buffer(val=".")
        panel.draw(target)
        assert "".join(target.buffer[0]) == expected
    finally:
        panel.close()


def test_styled_background_and_border_cells_remain_single_cells():
    panel = Panel(
        ImageEffect(""),
        size=(4, 1),
        title="é",
        border_color=120,
        border_background=235,
        background="\x1b[44m \x1b[0m",
    )
    panel.start()
    try:
        target = Buffer(3, 6)
        panel.draw(target)
        assert target.buffer[1][1] == "\x1b[44m \x1b[0m"
        assert "38;5;120" in target.buffer[0][2]
        assert plain(target)[0][2] == "é"
        assert all(len(cell) == 1 for row in plain(target) for cell in row)
    finally:
        panel.close()


@pytest.mark.parametrize("bounds", [(2, 2, 1, 1), (2, 2, 0, 0)])
def test_oversized_panel_anchors_at_bounds_origin_and_empty_bounds_hide_it(bounds):
    panel = Panel(
        ImageEffect("abc"),
        size=(3, 2),
        bounds=bounds,
        bounce=True,
        position=(-50, 40),
        velocity=(10, -30),
    )
    panel.start()
    try:
        panel.update(1234)
        assert panel.position == (2, 2)
        target = Buffer(5, 5).clear_buffer(val=".")
        panel.draw(target)
        expected = [list(".....") for _ in range(5)]
        if bounds[2]:
            expected[2][2] = "+"
        assert target.buffer == expected
    finally:
        panel.close()


def test_bounds_clip_without_bouncing_and_layer_can_clip_again():
    panel = Panel(
        ImageEffect("abcd", x=0, y=0),
        size=(4, 1),
        border=False,
        bounds=(1, 0, 3, 1),
        velocity=(-1, 0),
    )
    scene = Scene(Layer(panel, region=(2, 0, 1, 1)))
    scene.start()
    try:
        scene.update(1)
        assert panel.position == (-1, 0)
        target = Buffer(1, 5).clear_buffer(val=".")
        scene.draw(target)
        assert target.buffer == [list("..d..")]
    finally:
        scene.close()


def test_child_tick_cap_does_not_discard_panel_motion_and_offscreen_updates_continue():
    child = Marker()
    panel = Panel(
        child,
        size=(6, 2),
        position=(100, 100),
        velocity=(10, -2),
        updates_per_second=30,
        max_catch_up=2,
    )
    panel.start()
    try:
        panel.update(10)
        panel.draw(Buffer(1, 1))
        assert panel.position == (200, 80)
        assert child.ticks == [1 / 30] * 2
        panel.update(0)
        assert len(child.ticks) == 2
    finally:
        panel.close()


def test_completion_is_forwarded_and_capture_can_hold_or_exit():
    def make():
        return Panel(TimedOverlay(ImageEffect("x"), duration=0.1), size=(1, 1))

    panel = make()
    assert panel.finished is False
    assert (
        capture(
            panel, on_frame=lambda frame: None, width=3, height=3, frames=60, fps=30
        )
        < 60
    )
    assert panel.finished is True
    assert (
        capture(
            make(),
            on_frame=lambda frame: None,
            width=3,
            height=3,
            frames=60,
            fps=30,
            on_complete="hold",
        )
        == 60
    )


def test_close_before_start_releases_supplied_child_without_calling_factory():
    child = Marker()
    panel = Panel(child, size=(6, 2))
    panel.close()
    panel.close()
    assert child.closes == 1
    with pytest.raises(RuntimeError, match="single-use"):
        panel.start()
    calls = []
    lazy = Panel(effect_factory=lambda buffer: calls.append(buffer), size=(1, 1))
    lazy.close()
    assert calls == []


@pytest.mark.parametrize("method", ["update", "draw"])
def test_player_cleans_up_panel_when_child_fails(method, monkeypatch):
    child = Marker()

    def fail(*args):
        raise RuntimeError("child failed")

    monkeypatch.setattr(child, method, fail)
    with pytest.raises(RuntimeError, match="child failed"):
        capture(
            Panel(child, size=(6, 2)),
            on_frame=lambda frame: None,
            width=10,
            height=6,
            frames=3,
        )
    assert child.closes == 1


def test_wrong_factory_size_is_rejected_and_acquired_child_is_closed():
    child = Marker()
    panel = Panel(effect_factory=lambda buffer: child, size=(1, 1))
    with pytest.raises(ValueError, match="buffer dimensions"):
        panel.start()
    panel.close()
    assert child.closes == 1 and not child._started
    with pytest.raises(ValueError, match="buffer dimensions"):
        Panel(Marker(), size=(2, 6))


def test_invalid_factory_result_or_exception_does_not_allow_restart():
    def fail(buffer):
        raise LookupError("factory failed")

    for factory, error in [(fail, LookupError), (lambda buffer: object(), TypeError)]:
        panel = Panel(effect_factory=factory, size=(1, 1))
        with pytest.raises(error):
            panel.start()
        panel.close()
        assert panel.animation is None
        with pytest.raises(RuntimeError, match="single-use"):
            panel.start()


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"size": (0, 2)}, ValueError),
        ({"size": (2, -1)}, ValueError),
        ({"size": (True, 2)}, TypeError),
        ({"size": [2, 2]}, TypeError),
        ({"size": (1, 2, 3)}, TypeError),
        ({"size": (1.5, 2)}, TypeError),
        ({"position": (float("inf"), 0)}, ValueError),
        ({"velocity": (0, float("nan"))}, ValueError),
        ({"position": (True, 0)}, TypeError),
        ({"velocity": [1, 2]}, TypeError),
        ({"border": 1}, TypeError),
        ({"bounce": "yes"}, TypeError),
        ({"bounce": True}, ValueError),
        ({"bounds": (0, 0, -1, 2)}, ValueError),
        ({"bounds": (0, 0, 1.5, 2)}, TypeError),
        ({"bounds": (0, 0)}, TypeError),
        ({"border": False, "title": "oops"}, ValueError),
        ({"title": "two\nlines"}, ValueError),
        ({"title": "界"}, ValueError),
        ({"title": "\x1b[31mred"}, ValueError),
        ({"title": 42}, TypeError),
        ({"background": "ab"}, ValueError),
        ({"background": "\x1b[2J "}, ValueError),
        ({"border_color": 256}, ValueError),
        ({"border_background": -1}, ValueError),
        ({"border_color": True}, TypeError),
        ({"border_background": "blue"}, TypeError),
        ({"updates_per_second": 0}, ValueError),
        ({"updates_per_second": -1}, ValueError),
        ({"updates_per_second": float("inf")}, ValueError),
        ({"updates_per_second": True}, TypeError),
        ({"max_catch_up": 0}, ValueError),
        ({"max_catch_up": 1.5}, TypeError),
    ],
)
def test_invalid_options_fail_before_factory_is_called(kwargs, error):
    calls = []
    options = {"size": (2, 2), **kwargs}
    with pytest.raises(error):
        Panel(effect_factory=lambda buffer: calls.append(buffer), **options)
    assert not calls


def test_requires_exactly_one_valid_child_source():
    with pytest.raises(ValueError, match="exactly one"):
        Panel(size=(1, 1))
    with pytest.raises(ValueError, match="exactly one"):
        Panel(
            ImageEffect("x"),
            effect_factory=lambda buffer: ImageEffect("y"),
            size=(1, 1),
        )
    with pytest.raises(TypeError, match="implement Animation"):
        Panel("snow", size=(1, 1))
    with pytest.raises(TypeError, match="callable"):
        Panel(effect_factory=42, size=(1, 1))


def test_draw_and_update_require_started_open_panel():
    panel = Panel(ImageEffect("x"), size=(1, 1))
    for operation in (lambda: panel.draw(Buffer(3, 3)), lambda: panel.update(0)):
        with pytest.raises(RuntimeError, match="must be started"):
            operation()
    panel.start()
    panel.close()
    for operation in (lambda: panel.draw(Buffer(3, 3)), lambda: panel.update(0)):
        with pytest.raises(RuntimeError, match="must be started"):
            operation()


def test_large_update_reflects_multiple_times_and_initial_position_clamps():
    panel = Panel(
        ImageEffect("x"),
        size=(1, 1),
        border=False,
        bounds=(10, 5, 11, 6),
        position=(-100, 100),
        velocity=(-7, 3),
        bounce=True,
    )
    assert panel.position == (10, 10)
    panel.start()
    try:
        panel.update(10)
        assert panel.position == (20, 10)
        assert panel.velocity == (-7.0, 3.0)
    finally:
        panel.close()


def test_overflowing_motion_rejects_update_before_advancing_child():
    child = Marker()
    panel = Panel(child, size=(6, 2), velocity=(1e308, 0))
    panel.start()
    try:
        with pytest.raises(ValueError, match="finite coordinates"):
            panel.update(100)
        assert panel.position == (0, 0) and child.ticks == []
    finally:
        panel.close()


@pytest.mark.parametrize("dt", [-1, float("inf"), float("nan"), True, "fast"])
def test_invalid_update_does_not_move_panel_or_update_child(dt):
    child = Marker()
    panel = Panel(child, size=(6, 2), velocity=(1, 1))
    panel.start()
    try:
        with pytest.raises((TypeError, ValueError)):
            panel.update(dt)
        assert panel.position == (0, 0) and child.ticks == []
    finally:
        panel.close()
