"""Keyboard/lifecycle tests use synthetic animations, never audio devices."""

import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import Buffer, CallbackEffect, Player, Screen
from bruhanimate.demos import audio_demo
from bruhanimate.demos._showcase import Showcase


def make_showcase(*, failing=None):
    events = []

    class Mode(CallbackEffect):
        def __init__(self, name):
            super().__init__(lambda buffer: None)
            self.name = name
            self.active = False

        def start(self):
            assert not any(mode.active for _, mode in showcase.phases)
            self.active = True
            events.append((self.name, "start"))
            if self.name == failing:
                raise RuntimeError("capture startup failed")

        def close(self):
            if self.active:
                events.append((self.name, "close"))
                self.active = False

    showcase = Showcase(
        [(name, Mode(name)) for name in ("Bars", "Mirror", "Waveform")],
        title="Audio",
        duration=10,
        keyboard_navigation=True,
    )
    return showcase, events


def test_arrows_wrap_reset_timer_and_close_before_start():
    showcase, events = make_showcase()
    showcase.start()
    try:
        showcase.update(9.99)
        assert not showcase.handle_event(Screen.KEY_LEFT)
        assert showcase.index == 2 and showcase.elapsed == 0
        assert events == [("Bars", "start"), ("Bars", "close"), ("Waveform", "start")]
        assert not showcase.handle_event(Screen.KEY_RIGHT)
        assert showcase.index == 0
        showcase.update(0.1)
        assert showcase.index == 0
        showcase.update(10)
        showcase.update(0)
        assert showcase.index == 1
        showcase.resize((100, 4))
        assert showcase.index == 1
        frame = Buffer(4, 100)
        showcase.draw(frame)
        text = "".join(frame.buffer[0])
        assert "Mirror" in text and "left previous" in text and "right next" in text
    finally:
        showcase.close()
        showcase.close()
    assert not any(mode.active for _, mode in showcase.phases)
    assert events[-1] == ("Mirror", "close")


def test_navigation_before_start_or_after_close_does_not_acquire_capture():
    showcase, events = make_showcase()
    showcase.handle_event(Screen.KEY_RIGHT)
    assert showcase.index == 1 and events == []
    showcase.start()
    showcase.close()
    before = list(events)
    showcase.handle_event(Screen.KEY_RIGHT)
    assert events == before and showcase.scene is None


@pytest.mark.parametrize("event", [ord("q"), ord("Q"), Screen.KEY_ESCAPE, 27, 3])
def test_quit_keys_and_unbound_keys(event):
    showcase, events = make_showcase()
    assert showcase.handle_event(event)
    assert not showcase.handle_event(ord("x"))
    assert showcase.index == 0 and events == []


def test_audio_run_routes_player_input_and_restores_screen(monkeypatch):
    showcase, events = make_showcase()
    monkeypatch.setattr(audio_demo, "build", lambda buffer, **kwargs: showcase)
    screen = RecordingScreen([Screen.KEY_RIGHT, None, Screen.KEY_LEFT, None, ord("q")])
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    clock = Clock()
    original_run = Player.run

    def run(player):
        player.clock, player.sleep = clock, clock.sleep
        return original_run(player)

    monkeypatch.setattr(Player, "run", run)
    assert audio_demo.run(frames=10) == 2
    assert screen.closed
    assert events == [
        ("Bars", "start"),
        ("Bars", "close"),
        ("Mirror", "start"),
        ("Mirror", "close"),
        ("Bars", "start"),
        ("Bars", "close"),
    ]


def test_switch_start_failure_cleans_new_and_old_modes():
    showcase, events = make_showcase(failing="Mirror")
    screen = RecordingScreen([Screen.KEY_RIGHT])
    with pytest.raises(RuntimeError, match="startup failed"):
        Player(screen, showcase, frames=1, event_handler=showcase.handle_event).run()
    assert events == [
        ("Bars", "start"),
        ("Bars", "close"),
        ("Mirror", "start"),
        ("Mirror", "close"),
    ]
    assert showcase.scene is None


def test_audio_build_exposes_navigation_and_zero_frames_stays_inert(monkeypatch):
    showcase = audio_demo.build(Buffer(3, 5))
    assert [hint.key for hint in showcase.bindings.hints()] == [
        "left",
        "right",
        "q",
        "c",
    ]
    assert all(not effect._started for _, effect in showcase.phases)
    assert all(
        effect.compact
        for label, effect in showcase.phases
        if label in ("Bars", "Mirror")
    )
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: RecordingScreen()))
    monkeypatch.setattr(
        audio_demo,
        "build",
        lambda buffer, **kwargs: pytest.fail("zero frames built audio"),
    )
    assert audio_demo.run(frames=0) == 0


def test_curated_audio_demo_explains_mapping_without_advancing_on_draw(monkeypatch):
    from bruhanimate import AudioEffect

    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    showcase = audio_demo.build(Buffer(8, 80))
    assert [label for label, _ in showcase.phases] == [
        "Objects",
        "Tiles",
        "Glow",
        "Bars",
        "Mirror",
        "Waveform",
        "Spectrum",
    ]
    showcase.start()
    try:
        first, second = Buffer(8, 80), Buffer(8, 80)
        showcase.draw(first)
        showcase.draw(second)
        assert first.buffer == second.buffer
        assert "Audio 1/7: Objects" in "".join(first.buffer[0])
        assert "right next" in "".join(first.buffer[0])
        assert "Bass grows blocks 3x3 to touching" in "".join(first.buffer[-1])
        assert showcase.index == 0 and showcase.elapsed == 0
    finally:
        showcase.close()


def test_audio_never_auto_cycles_and_all_modes_can_be_selected_after_resize(
    monkeypatch,
):
    from bruhanimate import AudioEffect

    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    showcase = audio_demo.build(Buffer(8, 80))
    assert showcase.duration is None
    showcase.start()
    try:
        for i in range(len(showcase.phases)):
            showcase.update(3600)
            showcase.update(3600)
            assert showcase.index == i
            showcase.resize((12, 6))
            showcase.update(3600)
            assert showcase.index == i
            assert all(
                effect._viewport == showcase.frame.screen_size
                for _, effect in showcase.phases
            )
            assert sum(effect._started for _, effect in showcase.phases) == 1
            showcase.draw(Buffer(6, 12))
            assert not showcase.handle_event(Screen.KEY_RIGHT)
        assert showcase.index == 0
        assert not showcase.handle_event(Screen.KEY_LEFT)
        assert showcase.index == len(showcase.phases) - 1
    finally:
        showcase.close()
    assert all(not effect._started for _, effect in showcase.phases)


@pytest.mark.parametrize("computer", ["classic", "expanded", "box"])
@pytest.mark.parametrize(
    "size", [(80, 34), (113, 41), (12, 10), (9, 5), (2, 2), (1, 1)]
)
def test_computer_projects_only_inside_screen_and_keeps_captions_clear(computer, size):
    from bruhanimate.demos._computer import ComputerFrame

    frame = ComputerFrame(size, computer)
    width, height = frame.screen_size
    assert width >= 1 and height >= 1
    screen = Buffer(height, width)
    screen.clear_buffer(val="X")
    first, second = Buffer(size[1], size[0]), Buffer(size[1], size[0])
    frame.draw(first, screen)
    frame.draw(second, screen)
    assert first.buffer == second.buffer
    opening = {(x, y) for x, y, _, _ in frame.cells}
    assert all(0 <= x < size[0] and 1 <= y < size[1] - 1 for x, y in opening)
    assert all(0 <= sx < width and 0 <= sy < height for _, _, sx, sy in frame.cells)
    for y, row in enumerate(first.buffer):
        for x, cell in enumerate(row):
            assert (cell == "X") == ((x, y) in opening)
    assert all(cell == "X" for row in screen.buffer for cell in row)


def test_classic_computer_preserves_bezel_and_projects_each_bar_to_sloped_base():
    from bruhanimate import get_image
    from bruhanimate.demos._computer import COMPUTER, ComputerFrame, _origin

    original = tuple(get_image("computer"))
    frame = ComputerFrame((80, 34), "classic")
    screen = Buffer(frame.screen_size[1], frame.screen_size[0])
    screen.clear_buffer(val="X")
    screen.put_at(0, 0, "T" * screen.width())
    screen.put_at(0, screen.height() - 1, "B" * screen.width())
    output = Buffer(34, 80)
    frame.draw(output, screen)
    left, top = _origin(output)
    for y, row in enumerate(COMPUTER):
        for x, glyph in enumerate(row):
            if glyph != " ":
                assert f"m{glyph}\x1b[0m" in output.get_char(left + x, top + y)
    for x in {x for x, _, _, _ in frame.cells}:
        ys = [y for px, y, _, _ in frame.cells if px == x]
        assert output.get_char(x, min(ys)) == "T"
        assert output.get_char(x, max(ys)) == "B"
    assert tuple(get_image("computer")) == original


def test_computer_toggle_and_resize_keep_live_audio_and_mode(monkeypatch):
    from bruhanimate import AudioEffect, BaseEffect

    starts, closes = [], []

    def start(effect):
        starts.append(effect)
        BaseEffect.start(effect)

    def close(effect):
        closes.append(effect)
        BaseEffect.close(effect)

    monkeypatch.setattr(AudioEffect, "start", start)
    monkeypatch.setattr(AudioEffect, "close", close)
    showcase = audio_demo.build(Buffer(34, 80))
    assert not starts
    showcase.start()
    try:
        active = showcase.phases[0][1]
        assert (
            active.buffer.width(),
            active.buffer.height(),
        ) == showcase.frame.screen_size
        active._bars[:] = 0.4
        phase = active._object_phase
        assert showcase.frame.active_style == "classic"
        assert not showcase.handle_event(ord("c"))
        assert showcase.frame.active_style == "expanded"
        assert showcase.computer == "expanded"
        assert not showcase.handle_event(ord("c"))
        assert showcase.frame.active_style == "box"
        assert showcase.computer == "box"
        assert not showcase.handle_event(ord("C"))
        assert showcase.frame.active_style == "classic"
        for size, expected in (((20, 8), "box"), ((80, 34), "classic")):
            showcase.resize(size)
            assert showcase.frame.active_style == expected
            assert showcase.computer == "classic"
            first, second = Buffer(size[1], size[0]), Buffer(size[1], size[0])
            showcase.draw(first)
            showcase.draw(second)
            assert first.buffer == second.buffer
            assert active._object_phase == phase
            assert all(abs(value - 0.4) < 1e-12 for value in active._bars)
            assert showcase.index == 0
        assert starts == [active] and not closes
        assert not showcase.handle_event(Screen.KEY_RIGHT)
        assert closes == [active] and len(starts) == 2
    finally:
        showcase.close()
    assert closes == starts


def test_audio_capture_errors_remain_readable_outside_small_monitor(monkeypatch):
    from bruhanimate import AudioEffect, BaseEffect

    monkeypatch.setattr(AudioEffect, "start", BaseEffect.start)
    showcase = audio_demo.build(Buffer(34, 80))
    showcase.start()
    try:
        message = (
            "Audio error: optional capture backend is missing; install the audio extra"
        )
        showcase.phases[0][1]._error = message
        output = Buffer(34, 80)
        showcase.draw(output)
        assert message in "".join(output.buffer[-1])
    finally:
        showcase.close()


def test_computer_style_is_validated_before_capture():
    with pytest.raises(ValueError, match="computer"):
        audio_demo.build(Buffer(34, 80), computer="unknown")


def test_expanded_art_preserves_original_sections_and_enlarges_blank_opening():
    from bruhanimate.demos._computer import COMPUTER, ComputerFrame, _expand_computer

    art, spans = _expand_computer(30, 12)
    assert len(art) == len(COMPUTER) + 12
    restored_rows = art[:8] + art[20:]
    assert tuple((row[:33] + row[63:]).rstrip() for row in restored_rows) == COMPUTER
    for y, start, stop in spans:
        assert art[y][start:stop] == " " * (stop - start)
    classic = ComputerFrame((120, 48), "classic")
    large = ComputerFrame((120, 48), "expanded")
    assert large.screen_size[0] > classic.screen_size[0] * 2
    assert large.screen_size[1] > classic.screen_size[1] * 2
    assert large.active_style == "expanded"


@pytest.mark.parametrize("computer", ["classic", "expanded", "box"])
def test_computer_body_hides_snow_but_preserves_background_outside(computer):
    from bruhanimate.demos._computer import ComputerFrame

    frame = ComputerFrame((120, 48), computer)
    target = Buffer(48, 120)
    target.clear_buffer(val="~")  # Snow sentinel everywhere.
    screen = Buffer(frame.screen_size[1], frame.screen_size[0])
    screen.clear_buffer(val="X")
    frame.draw(target, screen)
    assert target.get_char(0, 1) == "~"
    for x, y, text in frame.body:
        start = len(text) - len(text.lstrip())
        assert all(
            target.get_char(x + col, y) != "~" for col in range(start, len(text))
        )
    assert all(target.get_char(x, y) == "X" for x, y, _, _ in frame.cells)


def test_snow_has_independent_clock_and_survives_mode_and_style_changes(monkeypatch):
    from unittest.mock import Mock

    from bruhanimate import AudioEffect, BaseEffect

    monkeypatch.setattr(AudioEffect, "start", BaseEffect.start)
    showcase = audio_demo.build(Buffer(48, 120))
    snow = showcase._background.layers[0].animation
    update = Mock(wraps=snow.update)
    monkeypatch.setattr(snow, "update", update)
    showcase.start()
    try:
        for _ in range(30):
            showcase.update(1 / 30)
        assert update.call_count == 15
        assert all(call.args == (1 / 15,) for call in update.call_args_list)
        showcase.update(1 / 30)
        clock = showcase._background._elapsed.copy()
        rng = snow.rng.getstate()
        before = [row.copy() for row in snow.buffer.buffer]
        showcase.handle_event(Screen.KEY_RIGHT)
        showcase.handle_event(ord("c"))
        assert snow._started
        assert snow.rng.getstate() == rng
        assert snow.buffer.buffer == before
        assert showcase._background._elapsed == clock
        first, second = Buffer(48, 120), Buffer(48, 120)
        showcase.draw(first)
        showcase.draw(second)
        assert first.buffer == second.buffer
        assert snow.rng.getstate() == rng
        showcase.resize((80, 34))
        assert (snow.buffer.width(), snow.buffer.height()) == (80, 34)
        assert snow._started
    finally:
        showcase.close()
        showcase.close()
    assert not snow._started


def test_failed_audio_start_closes_background_snow(monkeypatch):
    from bruhanimate import AudioEffect

    def fail(effect):
        raise RuntimeError("capture failed")

    monkeypatch.setattr(AudioEffect, "start", fail)
    showcase = audio_demo.build(Buffer(34, 80))
    with pytest.raises(RuntimeError, match="capture failed"):
        showcase.start()
    assert not showcase._background.layers[0].animation._started
    assert showcase.scene is None
    showcase.close()
