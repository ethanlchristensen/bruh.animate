import pytest

from bruhanimate import (
    Buffer,
    GridViewport,
    ImageEffect,
    Layer,
    PathEffect,
    PulseEffect,
    RippleEffect,
    Scene,
)
from bruhanimate.demos.routing_demo import BOARD, build_scene, find_route


def render(effect, width=9, height=7):
    buffer = Buffer(height, width).clear_buffer(val=None)
    effect.draw(buffer)
    return buffer


def test_path_order_trace_trail_hold_and_completion():
    points = [(0, 0), (1, 0), (1, 1), (2, 1)]
    effect = PathEffect(
        points, size=(3, 2), x=0, y=0, duration=3, trail=1, hold_duration=1
    )
    points.clear()
    assert effect.position == (0, 0)
    effect.update(2)
    assert effect.position == (1, 1)
    assert render(effect).buffer[0][:3] == [None, "*", None]
    assert render(effect).buffer[1][:3] == [None, "*", None]
    effect.update(1)
    assert not effect.finished and effect.position == (2, 1)
    effect.update(1)
    assert effect.finished and effect.position is None
    assert all(cell is None for row in render(effect).buffer for cell in row)
    trace = PathEffect(
        [(0, 0), (1, 0), (2, 0)], size=(3, 1), mode="trace", duration=2, hold_duration=1
    )
    trace.update(2)
    assert render(trace, 3, 1).buffer == [list("***")]


def test_path_no_interpolation_and_empty_or_single_cell():
    jump = PathEffect([(0, 0), (4, 0)], size=(5, 1), duration=1, hold_duration=1)
    jump.update(1)
    assert render(jump, 5, 1).buffer == [["*", None, None, None, "*"]]
    assert PathEffect([], size=(1, 1), repeat=True).finished
    point = PathEffect([(0, 0)], size=(1, 1), duration=1)
    assert point.position == (0, 0)
    point.update(0.5)
    assert point.position == (0, 0)


@pytest.mark.parametrize(
    "kind,args",
    [
        (PathEffect, ([(1, 1), (2, 1)],)),
        (PulseEffect, ((2, 1),)),
        (RippleEffect, ((2, 1),)),
    ],
)
def test_pure_draw_centering_repeat_gap_and_large_time(kind, args):
    effect = kind(
        *args, size=(5, 3), duration=1, repeat=True, repeat_delay=1, spacing=(2, 1)
    )
    effect.start()
    effect.start()
    effect.update(0.25)
    first = render(effect, 15, 9).buffer
    assert render(effect, 15, 9).buffer == first
    render(effect, 1, 1)
    assert render(effect, 15, 9).buffer == first
    effect.update(1)
    assert all(cell is None for row in render(effect).buffer for cell in row)
    effect.update(2000001)
    assert render(effect, 15, 9).buffer == first
    effect.close()
    effect.close()


def test_pulse_brightness_and_scene_restores_lower_layer():
    pulse = PulseEffect((0, 0), size=(1, 1), duration=1, cycles=1, colors=(22, 46, 231))
    scene = Scene(ImageEffect("A", x=0, y=0), Layer(pulse))
    scene.start()
    assert "22m" in render(scene, 1, 1).get_char(0, 0)
    scene.update(0.5)
    assert "231m" in render(scene, 1, 1).get_char(0, 0)
    scene.update(0.5)
    assert render(scene, 1, 1).get_char(0, 0) == "A"
    scene.close()


@pytest.mark.parametrize(
    "metric,count", [("manhattan", 4), ("chebyshev", 8), ("euclidean", 4)]
)
def test_ripple_metric_exact_ring(metric, count):
    effect = RippleEffect(
        (2, 2), size=(5, 5), radius=2, thickness=0.1, duration=2, metric=metric
    )
    effect.update(1)
    cells = render(effect, 5, 5).buffer
    assert sum(cell is not None for row in cells for cell in row) == count
    assert cells[2][2] is None
    effect.update(1)
    assert all(cell is None for row in render(effect, 5, 5).buffer for cell in row)


def test_ripple_visits_only_visible_board_cells(monkeypatch):
    calls = []
    original = GridViewport.put

    def put(self, x, y, glyph):
        calls.append((x, y))
        return original(self, x, y, glyph)

    monkeypatch.setattr(GridViewport, "put", put)
    ripple = RippleEffect((0, 0), size=(10**9, 10**9), radius=10**9, thickness=10**9)
    render(ripple, 3, 2)
    assert len(calls) == 6


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"size": (0, 1)}, ValueError),
        ({"duration": 0}, ValueError),
        ({"duration": True}, TypeError),
        ({"duration": float("inf")}, ValueError),
        ({"repeat": 1}, TypeError),
        ({"hold_duration": -1}, ValueError),
        ({"repeat_delay": -1}, ValueError),
        ({"x": 1.5}, TypeError),
        ({"spacing": (0, 1)}, ValueError),
        ({"glyph": "wide"}, ValueError),
        ({"mode": "jump"}, ValueError),
        ({"trail": -1}, ValueError),
    ],
)
def test_validation(kwargs, error):
    options = {"size": (2, 2)}
    options.update(kwargs)
    with pytest.raises(error):
        PathEffect([(0, 0)], **options)


def test_point_pulse_and_ripple_validation():
    with pytest.raises(ValueError):
        PathEffect([(2, 1)], size=(2, 2))
    with pytest.raises(TypeError):
        PathEffect([(True, 1)], size=(2, 2))
    with pytest.raises(ValueError):
        PulseEffect((0, 0), size=(1, 1), cycles=0)
    with pytest.raises(ValueError):
        PulseEffect((0, 0), size=(1, 1), colors=())
    with pytest.raises(ValueError):
        PulseEffect((0, 0), size=(1, 1), colors=(256,))
    with pytest.raises(ValueError):
        RippleEffect((0, 0), size=(1, 1), radius=0)
    with pytest.raises(ValueError):
        RippleEffect((0, 0), size=(1, 1), metric="square")


def test_route_fixture_and_complete_demo_cycle_survive_resize():
    route = find_route()
    assert BOARD[route[0][1]][route[0][0]] == "S"
    assert BOARD[route[-1][1]][route[-1][0]] == "E"
    assert all(BOARD[y][x] != "#" for x, y in route)
    assert all(abs(x - a) + abs(y - b) == 1 for (x, y), (a, b) in zip(route, route[1:]))
    scene = build_scene(Buffer(15, 50))
    scene.start()
    sequence = scene.layers[2].animation
    names = set()
    try:
        for _ in range(120):
            scene.update(0.1)
            names.add(sequence.phase_name)
            scene.resize((1, 1))
            render(scene, 1, 1)
            scene.resize((50, 15))
            render(scene, 50, 15)
        assert names == {
            "Source pulse",
            "Trace route",
            "Moving packet",
            "Arrival ripple",
        }
    finally:
        scene.close()
    with pytest.raises(ValueError):
        find_route(["S#E"])
