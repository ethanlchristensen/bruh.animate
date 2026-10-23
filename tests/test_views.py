from unittest.mock import Mock

import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import (
    Buffer,
    CallbackEffect,
    FocusGroup,
    FocusTarget,
    Label,
    LogView,
    Panel,
    Playback,
    Player,
    ScrollView,
    TextStyle,
)


def render(view, width=None, height=None):
    width = view.size[0] if width is None else width
    height = view.size[1] if height is None else height
    buffer = Buffer(height, width).clear_buffer(val=".")
    view.draw(buffer)
    return buffer


def rows(view):
    return ["".join(row) for row in render(view).buffer]


def test_scroll_view_paints_clipped_cells_preserves_transparency_and_old_frames():
    def draw(buffer):
        buffer.put_at(0, 0, "abcdef")
        buffer.put_at(0, 1, "gh ijk")
        buffer.put_char(2, 2, "\x1b[31mx\x1b[0m")

    child = CallbackEffect(draw)
    child.update = Mock()
    view = ScrollView(child, size=(3, 2), content_size=(6, 3), background=None)
    view.start()
    first = render(view, 5, 3)
    snapshot = [row[:] for row in first.buffer]
    assert first.buffer == [list("abc.."), list("gh .."), list(".....")]
    view.scroll_to((2, 1))
    second = render(view)
    assert second.buffer == [list(" ij"), ["\x1b[31mx\x1b[0m", ".", "."]]
    assert render(view).buffer == second.buffer and first.buffer == snapshot
    child.update.assert_not_called()
    view.set_visible(False)
    assert rows(view) == ["...", "..."]
    view.update(0.25)
    child.update.assert_called_once_with(0.25)
    view.close()


def test_scroll_view_background_and_smaller_content_or_destination():
    view = ScrollView(
        Label("A", fill=False), size=(5, 3), content_size=(2, 1), background="-"
    )
    view.start()
    assert rows(view) == ["A----", "-----", "-----"]
    assert render(view, 1, 1).buffer == [["A"]]
    assert render(view, 0, 0).buffer == []
    view.scroll_to((999, 999))
    assert view.offset == (0, 0)
    view.close()


def test_scroll_commands_clamp_and_pages_overlap():
    view = ScrollView(Label("x"), size=(4, 3), content_size=(10, 10))
    view.page_down()
    assert view.offset == (0, 2)
    view.scroll_by(dx=100, dy=100)
    assert view.offset == (6, 7)
    view.page_up()
    assert view.offset == (6, 5)
    view.end()
    assert view.offset == (6, 7)
    view.home()
    assert view.offset == (0, 0)
    view.resize((1, 1))
    view.page_down()
    assert view.offset == (0, 1)
    view.resize((100, 100))
    assert view.offset == (0, 0)
    view.close()


def test_resize_changes_viewport_only_and_content_size_is_explicit():
    child = Label("x")
    child.resize = Mock()
    child.start = Mock()
    child.close = Mock()
    view = ScrollView(child, size=(5, 2), content_size=(30, 10))
    view.set_content_size((20, 10))
    view.resize((6, 3))
    child.resize.assert_not_called()
    view.start()
    view.start()
    child.resize.assert_called_once_with((20, 10))
    child.start.assert_called_once()
    view.scroll_to((9, 5))
    view.resize((7, 4))
    assert view.offset == (9, 5)
    child.resize.assert_called_once()
    view.set_content_size((8, 5))
    assert view.offset == (1, 1) and view.content_size == (8, 5)
    assert child.resize.call_args.args == ((8, 5),)
    view.close()
    view.close()
    child.close.assert_called_once()


@pytest.mark.parametrize("fail", ["start", "resize", "set_visible"])
def test_scroll_start_failure_cleans_child_once(fail):
    child = Label("x")
    setattr(child, fail, Mock(side_effect=RuntimeError("failed")))
    child.close = Mock()
    view = ScrollView(child, size=(2, 2), content_size=(4, 4))
    with pytest.raises(RuntimeError, match="failed"):
        view.start()
    view.close()
    child.close.assert_called_once()
    with pytest.raises(RuntimeError):
        view.start()


def test_close_before_start_and_player_error_cleanup():
    child = Label("x")
    child.close = Mock()
    view = ScrollView(child, size=(2, 2), content_size=(4, 4))
    view.close()
    view.close()
    child.close.assert_called_once()
    child = CallbackEffect(Mock(side_effect=ValueError("draw failed")))
    child.close = Mock()
    view = ScrollView(child, size=(2, 2), content_size=(4, 4))
    with pytest.raises(ValueError, match="draw failed"):
        Player(RecordingScreen(), view, frames=1).run()
    child.close.assert_called_once()


def test_scroll_view_preserves_solver_iterator_queue_and_completion():
    calls = []

    def states():
        try:
            for value in range(2):
                calls.append(value)
                yield value
        finally:
            calls.append("closed")

    playback = Playback(
        states(), lambda state, buffer: buffer.put_at(0, 0, str(state)), paused=True
    )
    view = ScrollView(playback, size=(2, 1), content_size=(4, 2))
    view.start()
    playback.step()
    view.resize((3, 2))
    view.bindings.handle_event(-208)
    render(view)
    render(view)
    assert not calls
    view.update(0)
    assert calls == [0] and playback.paused and not view.finished
    playback.step()
    view.update(0)
    playback.step()
    view.update(0)
    assert view.finished and calls == [0, 1, "closed"]
    view.close()
    assert calls.count("closed") == 1


def test_log_follow_scroll_and_resume_only_on_end():
    log = LogView(size=(8, 2))
    log.append("one\ntwo\nthree")
    log.start()
    assert rows(log) == ["two     ", "three   "] and log.follow_tail
    log.page_up()
    assert rows(log) == ["one     ", "two     "] and not log.follow_tail
    log.append("four")
    assert rows(log) == ["one     ", "two     "]
    log.scroll_by(dy=100)
    assert log.at_bottom and not log.follow_tail
    log.append("five")
    assert not log.at_bottom and rows(log) == ["three   ", "four    "]
    assert log.bindings.handle_event(-201) is False
    assert log.follow_tail and rows(log) == ["four    ", "five    "]
    log.home()
    assert not log.follow_tail and log.offset == (0, 0)
    log.follow_tail = True
    assert log.at_bottom and log.follow_tail
    log.close()


def test_scrolling_up_at_top_suspends_follow_before_new_messages_arrive():
    log = LogView(size=(4, 2))
    log.scroll_by(dy=-1)
    assert not log.follow_tail
    log.append("a\nb\nc")
    assert log.offset == (0, 0)
    log.close()


def test_bounded_history_preserves_reading_anchor_and_clamps_if_evicted():
    log = LogView(size=(6, 2), max_lines=4, follow_tail=False)
    log.append("zero\none\ntwo\nthree")
    log.start()
    log.scroll_to((0, 1))
    log.append("four")
    assert log.lines == ("one", "two", "three", "four")
    assert rows(log) == ["one   ", "two   "] and log.offset == (0, 0)
    log.append("five\nsix")
    assert rows(log) == ["three ", "four  "]
    log.append("A\nB\nC\nD\nE")
    assert log.lines == ("B", "C", "D", "E") and log.line_count == 4
    assert rows(log) == ["B     ", "C     "]
    log.clear()
    assert log.lines == () and log.offset == (0, 0) and not log.follow_tail
    assert rows(log) == ["      ", "      "]
    log.close()


def test_wrapped_resize_preserves_logical_line_and_character_anchor():
    log = LogView(size=(4, 2), follow_tail=False)
    log.append("abcdefghi\nsecond\nlast")
    log.start()
    log.scroll_to((0, 1))
    assert rows(log) == ["efgh", "i   "]
    log.resize((2, 2))
    assert log.offset == (0, 2) and rows(log) == ["ef", "gh"]
    log.resize((6, 2))
    assert rows(log) == ["abcdef", "ghi   "]  # Row containing the same character.
    log.end()
    log.resize((3, 2))
    assert log.at_bottom and rows(log) == ["las", "t  "]
    log.resize((100, 20))
    assert log.offset == (0, 0) and log.at_bottom
    log.close()


def test_eviction_of_wrapped_anchor_preserves_next_oldest_logical_line():
    log = LogView(size=(2, 1), max_lines=2, follow_tail=False)
    log.append("abcdef\nnext")
    log.start()
    log.scroll_to((0, 2))
    log.append("last")
    assert rows(log) == ["ne"] and log.offset == (0, 0)
    log.close()


def test_log_none_wrap_horizontal_scrolling_and_newlines():
    log = LogView(size=(3, 2), wrap="none", follow_tail=False)
    log.append("abcdef\n\nz\n")
    log.start()
    assert log.lines == ("abcdef", "", "z", "") and log.content_size == (6, 4)
    log.scroll_by(dx=2)
    assert rows(log) == ["cde", "   "]
    log.resize((5, 2))
    assert log.offset == (1, 0)
    log.clear()
    log.append("")
    assert log.line_count == 1 and log.offset == (0, 0)
    log.close()


def test_log_pure_draw_style_fill_and_invalid_append_preserve_old_frame():
    log = LogView(size=(3, 2), fill=False, style=TextStyle(foreground=117))
    log.append("a b")
    log.start()
    first = render(log, 4, 3)
    snapshot = [row[:] for row in first.buffer]
    assert first.buffer[0] == [
        "\x1b[38;5;117ma\x1b[0m",
        "\x1b[38;5;117m \x1b[0m",
        "\x1b[38;5;117mb\x1b[0m",
        ".",
    ]
    assert first.buffer[1:] == [list("...."), list("....")]
    before = (log.lines, log.offset, log.follow_tail)
    assert render(log, 4, 3).buffer == snapshot
    assert (log.lines, log.offset, log.follow_tail) == before
    with pytest.raises(ValueError):
        log.append("good\nbad\t")
    assert (log.lines, log.offset, log.follow_tail) == before
    log.append("new")
    assert first.buffer == snapshot
    log.close()


def test_focused_scroll_bindings_only_affect_selected_view_and_do_not_quit():
    a, b = LogView(size=(3, 2)), LogView(size=(3, 2))
    a.append("a\nb\nc")
    b.append("x\ny\nz")
    one, two = FocusTarget("one", a.bindings), FocusTarget("two", b.bindings)
    group = FocusGroup(one, two)
    first, second = Panel(a, size=(3, 2), focus=one), Panel(b, size=(3, 2), focus=two)
    second.start()
    first.start()
    group.focus("one")
    clock = Clock()
    screen = RecordingScreen(events=[-204, 9, -200, None, ord("q")])
    assert (
        Player(
            screen,
            first,
            event_handler=group.handle_event,
            clock=clock,
            sleep=clock.sleep,
        ).run()
        == 1
    )
    assert not a.follow_tail and not b.follow_tail
    assert a.offset == (0, 0) and b.offset == (0, 0)
    second.close()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LogView(size=(0, 1)),
        lambda: LogView(size=(1, True)),
        lambda: LogView(size=(2, 2), max_lines=0),
        lambda: LogView(size=(2, 2), max_lines=True),
        lambda: LogView(size=(2, 2), wrap="word"),
        lambda: LogView(size=(2, 2), follow_tail=1),
        lambda: LogView(size=(2, 2), style="blue"),
        lambda: LogView(size=(2, 2), fill=1),
        lambda: ScrollView("text", size=(2, 2), content_size=(3, 3)),
        lambda: ScrollView(Label("x"), size=(2, 2), content_size=(0, 3)),
        lambda: ScrollView(
            Label("x"), size=(2, 2), content_size=(3, 3), background="XX"
        ),
    ],
)
def test_invalid_view_options_fail_early(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


@pytest.mark.parametrize(
    "operation",
    [
        lambda view: view.scroll_by(dx=True),
        lambda view: view.scroll_to((1.5, 0)),
        lambda view: view.resize((-1, 2)),
        lambda view: view.append(123),
        lambda view: view.append("界"),
        lambda view: view.append("\x1b[31mx"),
        lambda view: setattr(view, "follow_tail", 1),
    ],
)
def test_invalid_log_mutations_preserve_history_and_position(operation):
    log = LogView(size=(3, 2))
    log.append("abc\ndef\nghi")
    before = log.lines, log.size, log.offset, log.follow_tail
    with pytest.raises((TypeError, ValueError)):
        operation(log)
    assert (log.lines, log.size, log.offset, log.follow_tail) == before
    log.close()


@pytest.mark.parametrize("kind", ["log", "scroll"])
def test_view_lifecycle_guards(kind):
    view = (
        LogView(size=(2, 2))
        if kind == "log"
        else ScrollView(Label("x"), size=(2, 2), content_size=(2, 2))
    )
    for operation in (lambda: view.update(0), lambda: render(view)):
        with pytest.raises(RuntimeError):
            operation()
    view.start()
    with pytest.raises(ValueError):
        view.update(float("nan"))
    view.close()
    view.close()
    for operation in (
        view.start,
        lambda: view.update(0),
        lambda: render(view),
        lambda: view.resize((3, 3)),
        view.home,
        view.end,
    ):
        with pytest.raises(RuntimeError):
            operation()
