import io
import json
import re
import weakref
from dataclasses import FrozenInstanceError

import pytest

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Frame,
    Player,
    Screen,
    capture,
    effects,
    record,
)


class Counter:
    def __init__(self, *, finished_at=None, fail=None):
        self.ticks = 0
        self.dts = []
        self.started = self.closed = 0
        self.finished_at = finished_at
        self.fail = fail

    def start(self):
        self.started += 1
        if self.fail == "start":
            raise RuntimeError("start failed")

    def update(self, dt):
        self.dts.append(dt)
        self.ticks += 1
        if self.fail == "update":
            raise RuntimeError("update failed")

    def draw(self, buffer):
        buffer.put_char(0, 0, str(self.ticks % 10))
        if self.fail == "draw":
            raise RuntimeError("draw failed")

    def close(self):
        self.closed += 1

    @property
    def finished(self):
        return self.finished_at is not None and self.ticks >= self.finished_at


@pytest.fixture(autouse=True)
def prohibit_terminal(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("headless capture touched the terminal")

    for name in (
        "__init__",
        "open",
        "show",
        "begin_frame",
        "print_at",
        "flush_frame",
        "close",
    ):
        monkeypatch.setattr(Screen, name, forbidden)


def test_streaming_immutable_snapshots_reuse_player_and_virtual_time(monkeypatch):
    animation = Counter()
    frames = []
    original = Player.run
    runs = []

    def run(player):
        runs.append(player)
        return original(player)

    monkeypatch.setattr(Player, "run", run)

    def consume(frame):
        assert frame.index == len(frames)
        assert animation.ticks == frame.index + 1  # delivered before the next update
        frames.append(frame)

    assert capture(animation, on_frame=consume, width=3, height=2, fps=4, frames=3) == 3
    assert len(runs) == 1
    assert animation.started == animation.closed == 1
    assert animation.dts == [0.25] * 3
    assert [frame.time for frame in frames] == [0, 0.25, 0.5]
    assert frames[0].text() == "1  \n   "
    assert frames[-1].cells == (("3", " ", " "), (" ", " ", " "))
    assert frames[0].width == 3 and frames[0].height == 2
    with pytest.raises(FrozenInstanceError):
        frames[0].time = 1
    with pytest.raises(TypeError):
        frames[0].cells[0][0] = "x"


@pytest.mark.parametrize("fps, ups, count, ticks", [(4, 2, 4, 2), (2, 20, 3, 21)])
def test_independent_update_rate_never_drops_offline_ticks(fps, ups, count, ticks):
    animation = Counter()
    capture(
        animation,
        on_frame=lambda f: None,
        fps=fps,
        updates_per_second=ups,
        frames=count,
    )
    assert animation.ticks == ticks
    assert animation.dts == [1 / ups] * ticks


@pytest.mark.parametrize(
    "fps, duration, count",
    [(4, 1, 4), (30, 1, 30), (60, 1, 60), (4, 0.3, 2), (4, 0, 0)],
)
def test_duration_excludes_deadline_frame(fps, duration, count):
    assert (
        capture(Counter(), on_frame=lambda f: None, fps=fps, duration=duration) == count
    )


def test_completion_exits_or_holds_and_limits_compete():
    assert capture(Counter(finished_at=2), on_frame=lambda f: None, frames=10) == 2
    assert (
        capture(
            Counter(finished_at=2),
            on_frame=lambda f: None,
            frames=10,
            on_complete="hold",
        )
        == 10
    )
    assert capture(Counter(), on_frame=lambda f: None, frames=2, duration=10) == 2


def test_factory_receives_dimensions_and_zero_does_not_construct():
    buffers = []
    animation = Counter()

    def factory(buffer):
        buffers.append(buffer)
        return animation

    assert capture(effect_factory=factory, on_frame=lambda f: None, frames=0) == 0
    assert not buffers
    capture(
        effect_factory=factory, on_frame=lambda f: None, frames=1, width=7, height=3
    )
    assert (buffers[0].width(), buffers[0].height()) == (7, 3)
    assert animation.closed == 1


@pytest.mark.parametrize("failure", ["start", "update", "draw", "callback"])
def test_failure_closes_owned_content(failure):
    animation = Counter(fail=failure)

    def consume(frame):
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match=failure):
        capture(animation, on_frame=consume, frames=3)
    assert animation.closed == 1


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"frames": -1},
        {"duration": float("nan")},
        {"duration": -1},
        {"frames": 2, "width": 0},
        {"frames": 2, "height": -1},
        {"frames": 2, "width": True},
        {"frames": 2, "fps": None},
        {"frames": 2, "fps": 0},
        {"frames": 2, "fps": float("inf")},
        {"frames": 2, "updates_per_second": 0},
        {"frames": 2, "background": "xx"},
    ],
)
def test_bad_configuration_never_starts_content_or_creates_output(options, tmp_path):
    animation = Counter()
    output = tmp_path / "invalid.cast"
    with pytest.raises((ValueError, TypeError)):
        record(animation, output, **options)
    assert not output.exists()
    assert animation.started == animation.closed == 0


def test_record_borrowed_stream_outputs_v2_diff_events_and_restores_styles():
    stream = io.StringIO()
    animation = Counter(finished_at=2)
    assert (
        record(
            animation, stream, width=2, height=1, frames=3, fps=4, on_complete="hold"
        )
        == 3
    )
    assert not stream.closed
    header, *events = map(json.loads, stream.getvalue().splitlines())
    assert header == {"version": 2, "width": 2, "height": 1}
    assert [event[0] for event in events] == [0, 0.25, 0.5, 0.5]
    assert all(event[1] == "o" for event in events)
    assert events[1][2] == "\x1b[1;1H\x1b[0m2"  # unchanged second cell is omitted
    assert events[-1][2] == "\x1b[0m\x1b[?7h\x1b[?25h"
    assert animation.closed == 1


def test_record_retains_duration_of_unchanged_frames():
    stream = io.StringIO()
    record("static", stream, width=1, height=1, frames=4, fps=4)
    header, initial, final = map(json.loads, stream.getvalue().splitlines())
    assert final[0] == 0.75


def test_cast_is_reproducible_and_preserves_unicode_sgr(tmp_path):
    first, second = tmp_path / "one.cast", tmp_path / "two.cast"
    effects.twinkle.record(first, preset="dense", seed=7, frames=6, width=8, height=4)
    effects.twinkle.record(second, preset="dense", seed=7, frames=6, width=8, height=4)
    assert first.read_bytes() == second.read_bytes()
    payload = first.read_text(encoding="utf-8")
    assert "\\u001b[" in payload
    assert all(json.loads(line) for line in payload.splitlines())
    with pytest.raises(FileExistsError):
        effects.snow.record(first, frames=1)
    record("static", first, frames=0, overwrite=True)
    assert len(first.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize("glyph", ["xx", "\n", "\x1b[2Jx", "界", "e\u0301"])
def test_record_rejects_unsupported_cell_glyphs_and_closes(glyph):
    animation = Counter()
    animation.draw = lambda buffer: buffer.put_char(0, 0, glyph)
    with pytest.raises(ValueError, match="single-cell"):
        record(animation, io.StringIO(), frames=1)
    assert animation.closed == 1


def test_snapshot_copies_mutable_cells_and_fills_transparency():
    class Cell:
        text = "x"

        def __str__(self):
            return self.text

    cell = Cell()
    snapshots = []

    def draw(buffer: Buffer):
        buffer.put_char(0, 0, cell)
        buffer.put_char(1, 0, None)

    capture(
        CallbackEffect(draw), on_frame=snapshots.append, width=2, height=1, frames=1
    )
    cell.text = "y"
    assert snapshots[0] == Frame(0, 0, (("x", " "),))


def test_stream_failure_closes_animation():
    class BrokenStream(io.StringIO):
        def write(self, text):
            if '"o"' in text:
                raise OSError("disk full")
            return super().write(text)

    animation = Counter()
    with pytest.raises(OSError, match="disk full"):
        record(animation, BrokenStream(), frames=2)
    assert animation.closed == 1


@pytest.mark.parametrize(
    "effect, options", [(object(), {}), (None, {"effect_factory": 1})]
)
def test_invalid_source_cannot_truncate_output(effect, options, tmp_path):
    output = tmp_path / "existing.cast"
    output.write_text("preserve me", encoding="utf-8")
    with pytest.raises(TypeError):
        record(effect, output, frames=1, overwrite=True, **options)
    assert output.read_text(encoding="utf-8") == "preserve me"


def test_capture_does_not_retain_frame_history():
    previous = None

    def consume(frame):
        nonlocal previous
        assert previous is None or previous() is None
        previous = weakref.ref(frame)

    assert capture(Counter(), on_frame=consume, frames=1000, width=1, height=1) == 1000
    assert previous() is None


def test_cast_reconstructs_composed_frames_at_correct_coordinates():
    from bruhanimate import ImageEffect, Layer, Scene

    def scene():
        def overlay(buffer):
            buffer.clear_buffer(val=" ")
            buffer.put_char(0, 0, "\x1b[31mX\x1b[0m")

        return Scene(
            ImageEffect(["abc", "def"]),
            Layer(CallbackEffect(overlay), transparent=True),
        )

    snapshots = []
    capture(scene(), on_frame=snapshots.append, frames=1, width=2, height=2)
    output = io.StringIO()
    record(scene(), output, frames=1, width=2, height=2)
    rows = [[" "] * 2 for _ in range(2)]
    x = y = 0
    # Interpret the supported terminal operations independently of the writer.
    for _, kind, data in map(json.loads, output.getvalue().splitlines()[1:]):
        assert kind == "o"
        for token in re.findall(r"\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]", data):
            if token.startswith("\x1b["):
                if token.endswith("H"):
                    position = token[2:-1]
                    y, x = (
                        (int(n) - 1 for n in position.split(";"))
                        if position
                        else (0, 0)
                    )
                elif token == "\x1b[2J":
                    rows = [[" "] * 2 for _ in range(2)]
            else:
                rows[y][x] = token
                x += 1
    assert rows == [
        [re.sub(r"\x1b\[[0-9;]*m", "", cell) for cell in row]
        for row in snapshots[-1].cells
    ]
