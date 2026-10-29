import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bruhanimate.bruhutil import bruhscreen


def test_unix_resume_defers_terminal_work_and_requests_one_redraw(unix_screen):
    screen_cls, curses = unix_screen
    screen = screen_cls.__new__(screen_cls)
    screen.screen = Mock()
    screen._re_sized = False
    screen._continue_handler()
    curses.reset_prog_mode.assert_not_called()
    screen.screen.refresh.assert_not_called()
    assert not screen.has_resized()
    assert screen.consume_redraw_request()
    curses.reset_prog_mode.assert_called_once()
    curses.curs_set.assert_called_once_with(0)
    screen.screen.clearok.assert_called_once_with(True)
    screen.screen.refresh.assert_called_once()
    assert screen._cur_x == screen._cur_y == -1
    assert not screen.consume_redraw_request()


@pytest.mark.parametrize("failure", ["write", "flush"])
def test_unix_output_errors_propagate_and_reset_batch(
    unix_screen, monkeypatch, failure
):
    from bruhanimate import Buffer, FramePresenter

    screen_cls, curses = unix_screen
    curses.tparm.return_value = b"\x1b[1;1H"
    screen = screen_cls.__new__(screen_cls)
    screen.width = screen.height = 1
    screen._cur_x = screen._cur_y = -1
    screen._move_y_x = b"cup"
    output = Mock()
    monkeypatch.setattr(sys, "stdout", output)
    getattr(output, failure).side_effect = OSError("output failed")
    presenter = FramePresenter(screen)
    with pytest.raises(OSError, match="output failed"):
        presenter.present(Buffer(1, 1).clear_buffer(val="X"))
    assert screen._frame_parts == [] and not screen._buffering
    assert screen._cur_x == screen._cur_y == -1
    assert presenter.last_displayed.buffer == [[None]]
    getattr(output, failure).side_effect = None
    presenter.present(Buffer(1, 1).clear_buffer(val="X"))
    assert output.write.call_args.args == ("\x1b[1;1HX",)
    assert output.write.call_count == 2


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
def test_windows_write_failure_is_not_committed_as_a_presented_frame():
    from bruhanimate import Buffer, FramePresenter

    screen = bruhscreen.Screen.__new__(bruhscreen.Screen)
    screen.width = screen.height = 1
    screen._current_x = screen._current_y = -1
    screen._stdout = Mock()
    screen._stdout.WriteConsole.side_effect = bruhscreen.pywintypes.error(
        6, "WriteConsole", "invalid handle"
    )
    presenter = FramePresenter(screen)
    with pytest.raises(bruhscreen.pywintypes.error):
        presenter.present(Buffer(1, 1).clear_buffer(val="X"))
    assert screen._frame_parts == [] and not screen._buffering
    assert screen._current_x == screen._current_y == -1
    assert presenter.last_displayed.buffer == [[None]]
    screen._stdout.WriteConsole.side_effect = None
    presenter.present(Buffer(1, 1).clear_buffer(val="X"))
    assert screen._stdout.WriteConsole.call_count == 2
    assert screen._stdout.WriteConsole.call_args.args == ("\x1b[1;1HX",)


@pytest.fixture
def unix_screen(monkeypatch):
    """Exercise the Unix implementation even when the test host is Windows."""
    curses = Mock()
    spec = importlib.util.spec_from_file_location(
        "test_unix_screen_backend", Path(bruhscreen.__file__)
    )
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "linux")
        patch.setitem(sys.modules, "curses", curses)
        spec.loader.exec_module(module)
    return module.Screen, curses


@pytest.mark.parametrize("buffered", [False, True])
@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
def test_unix_encoding_fallback_preserves_styles_and_cursor(
    unix_screen, monkeypatch, buffered, encoding
):
    screen_cls, curses = unix_screen
    curses.tparm.return_value = b"\x1b[1;1H"
    screen = screen_cls.__new__(screen_cls)
    screen._cur_x = screen._cur_y = -1
    screen._move_y_x = b"cup"
    screen._buffering = False
    screen._frame_parts = []
    raw = io.BytesIO()
    output = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", output)
    styled = "\x1b[31méΩ\x1b[0m"
    if buffered:
        screen.begin_frame()
    screen.print_at(styled, 0, 0, 2)
    screen.print_at("!", 2, 0, 1)
    screen.flush_frame()
    expected = ("\x1b[1;1H" + styled + "!").encode(encoding, errors="replace")
    assert raw.getvalue() == expected
    assert (screen._cur_x, screen._cur_y) == (3, 0)
    assert not screen._buffering
    # A subsequent frame must be usable and preserve the physical cursor.
    screen.begin_frame()
    screen.print_at("Z", 3, 0, 1)
    screen.flush_frame()
    assert raw.getvalue() == expected + b"Z"


def test_unix_show_restores_screen_without_prompting(unix_screen, monkeypatch):
    screen_cls, _ = unix_screen
    screen = Mock()
    monkeypatch.setattr(screen_cls, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=AssertionError("unexpected prompt"))
    )
    with pytest.raises(ValueError, match="callback failed"):
        screen_cls.show(Mock(side_effect=ValueError("callback failed")))
    screen.close.assert_called_once()


def test_unix_partial_initialization_restores_terminal(unix_screen, monkeypatch):
    screen_cls, curses = unix_screen
    signal_state = Mock()

    def fail(screen, window):
        screen.signal_state = signal_state
        raise ValueError("initialization failed")

    monkeypatch.setattr(screen_cls, "__init__", fail)
    with pytest.raises(ValueError, match="initialization failed"):
        screen_cls.open()
    signal_state.restore.assert_called_once()
    curses.endwin.assert_called_once()
    curses.nocbreak.assert_called_once()
    curses.echo.assert_called_once()


def test_unix_cleanup_attempts_every_restore_even_if_one_fails(unix_screen):
    screen_cls, curses = unix_screen
    screen = screen_cls.__new__(screen_cls)
    screen.screen = Mock()
    screen.signal_state = Mock()
    screen.signal_state.restore.side_effect = ValueError("signal restore failed")
    with pytest.raises(ValueError, match="signal restore failed"):
        screen.close()
    curses.endwin.assert_called_once()
    curses.echo.assert_called_once()


def test_explicit_end_prompt_accepts_normalized_input(monkeypatch):
    screen = Mock()
    screen.get_event.side_effect = [None, 10]
    sleep = Mock()
    monkeypatch.setattr(bruhscreen.time, "sleep", sleep)
    bruhscreen._wait_for_enter(screen)
    sleep.assert_called_once_with(0.05)


def test_unix_normalizes_named_keys_with_mock_curses(unix_screen):
    screen_cls, curses = unix_screen
    screen = screen_cls.__new__(screen_cls)
    screen.screen = Mock()
    names = {
        "KEY_BTAB": screen.KEY_BACK_TAB,
        "KEY_LEFT": screen.KEY_LEFT,
        "KEY_RIGHT": screen.KEY_RIGHT,
        "KEY_UP": screen.KEY_UP,
        "KEY_DOWN": screen.KEY_DOWN,
        "KEY_HOME": screen.KEY_HOME,
        "KEY_END": screen.KEY_END,
        "KEY_PPAGE": screen.KEY_PAGE_UP,
        "KEY_NPAGE": screen.KEY_PAGE_DOWN,
        "KEY_IC": screen.KEY_INSERT,
        "KEY_DC": screen.KEY_DELETE,
        "KEY_BACKSPACE": screen.KEY_BACK,
        "KEY_ENTER": 10,
        **{f"KEY_F{i}": getattr(screen, f"KEY_F{i}") for i in range(1, 13)},
    }
    curses.ERR = -1
    cases = {
        9: screen.KEY_TAB,
        27: screen.KEY_ESCAPE,
        8: screen.KEY_BACK,
        127: screen.KEY_BACK,
        13: 10,
        10: 10,
        32: 32,
        ord("q"): ord("q"),
        -1: None,
    }
    for code, (name, expected) in enumerate(names.items(), 300):
        setattr(curses, name, code)
        cases[code] = expected
    for raw, expected in cases.items():
        screen.screen.getch.return_value = raw
        assert screen.get_event() == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
def test_windows_normalizes_named_keys_with_mock_console():
    output, input_handle = Mock(), Mock()
    output.GetConsoleScreenBufferInfo.return_value = {
        "Window": SimpleNamespace(Left=0, Top=0, Right=79, Bottom=23)
    }
    screen = bruhscreen.Screen(output, input_handle, Mock(), 0)
    codes = bruhscreen.win32con
    cases = [
        (codes.VK_TAB, "\t", 0, screen.KEY_TAB),
        (codes.VK_TAB, "\t", codes.SHIFT_PRESSED, screen.KEY_BACK_TAB),
        (codes.VK_RETURN, "\r", 0, 10),
        (codes.VK_RIGHT, "\0", 0, screen.KEY_RIGHT),
        (codes.VK_ESCAPE, "\x1b", 0, screen.KEY_ESCAPE),
        (codes.VK_F1, "\0", 0, screen.KEY_F1),
        (ord("Q"), "q", 0, ord("q")),
        (ord("C"), "\x03", codes.LEFT_CTRL_PRESSED, 3),
    ]
    for virtual, char, modifiers, expected in cases:
        event = SimpleNamespace(
            EventType=bruhscreen.win32console.KEY_EVENT,
            Char=char,
            KeyDown=True,
            VirtualKeyCode=virtual,
            ControlKeyState=modifiers,
        )
        input_handle.PeekConsoleInput.return_value = [event]
        input_handle.ReadConsoleInput.return_value = [event]
        assert screen.get_event() == expected


def test_unix_resize_signal_only_marks_pending_and_refreshes_outside_handler(
    unix_screen, monkeypatch
):
    screen_cls, curses = unix_screen
    screen = screen_cls.__new__(screen_cls)
    screen.screen = Mock()
    screen._re_sized = False
    screen._resize_handler()
    assert screen.has_resized()
    curses.endwin.assert_not_called()
    curses.initscr.assert_not_called()
    monkeypatch.setattr(
        bruhscreen.os,
        "get_terminal_size",
        lambda fd: SimpleNamespace(columns=101, lines=31),
    )
    monkeypatch.setattr(sys, "stdout", Mock())
    assert screen.refresh_size()
    assert (screen.width, screen.height) == (101, 31)
    assert not screen.has_resized()
    assert screen._cur_x == screen._cur_y == -1
    curses.resizeterm.assert_called_once_with(31, 101)


def test_unix_empty_size_remains_pending(unix_screen, monkeypatch):
    screen_cls, curses = unix_screen
    screen = screen_cls.__new__(screen_cls)
    screen.width, screen.height = 80, 24
    screen._re_sized = True
    monkeypatch.setattr(
        bruhscreen.os,
        "get_terminal_size",
        lambda fd: SimpleNamespace(columns=0, lines=0),
    )
    monkeypatch.setattr(sys, "stdout", Mock())
    assert not screen.refresh_size()
    assert screen.has_resized() and (screen.width, screen.height) == (80, 24)
    curses.resizeterm.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
def test_windows_resize_acknowledges_new_size_and_invalidates_cursor():
    screen = bruhscreen.Screen.__new__(bruhscreen.Screen)
    screen._stdout = Mock()
    screen._last_width, screen._last_height = 80, 24
    screen._stdout.GetConsoleScreenBufferInfo.return_value = {
        "Window": SimpleNamespace(Left=0, Top=0, Right=99, Bottom=29)
    }
    assert screen.has_resized()
    assert screen.refresh_size()
    assert (screen.width, screen.height) == (100, 30)
    assert not screen.has_resized()
    assert screen._current_x == screen._current_y == -1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
@pytest.mark.parametrize("fail_at", ["input", "mode", "initialize", None])
def test_windows_open_restores_and_closes_partial_resources(monkeypatch, fail_at):
    old_out, output, input_handle = Mock(), Mock(), Mock()
    old_out.GetConsoleScreenBufferInfo.return_value = {"Size": (80, 24)}
    output.GetConsoleMode.return_value = 7
    input_handle.GetConsoleMode.return_value = 7
    console = SimpleNamespace(
        PyConsoleScreenBufferType=Mock(side_effect=[old_out, input_handle]),
        CreateConsoleScreenBuffer=Mock(return_value=output),
        ENABLE_WRAP_AT_EOL_OUTPUT=2,
        ENABLE_MOUSE_INPUT=16,
        ENABLE_PROCESSED_INPUT=1,
    )
    files = SimpleNamespace(
        CreateFile=Mock(
            side_effect=[1, RuntimeError("input failed")]
            if fail_at == "input"
            else [1, 2]
        ),
        GENERIC_READ=1,
        GENERIC_WRITE=2,
        FILE_SHARE_WRITE=4,
        FILE_SHARE_READ=8,
        OPEN_ALWAYS=16,
    )
    monkeypatch.setattr(bruhscreen, "win32console", console)
    monkeypatch.setattr(bruhscreen, "win32file", files)
    if fail_at == "mode":
        # First call changes the mode; second call restores it in rollback.
        input_handle.SetConsoleMode.side_effect = [RuntimeError("mode failed"), None]
    if fail_at == "initialize":
        monkeypatch.setattr(
            bruhscreen.Screen,
            "__init__",
            Mock(side_effect=RuntimeError("initialize failed")),
        )
    elif fail_at is None:

        def initialize(screen, stdout, stdin, previous, mode):
            screen._stdout, screen._stdin = stdout, stdin
            screen._old_out, screen._old_in = previous, mode

        monkeypatch.setattr(bruhscreen.Screen, "__init__", initialize)

    if fail_at:
        with pytest.raises(RuntimeError, match=f"{fail_at} failed"):
            bruhscreen.Screen.open()
    else:
        screen = bruhscreen.Screen.open()
        assert not output.Close.called
        screen.close()
        screen.close()
    old_out.SetConsoleActiveScreenBuffer.assert_called_once()
    old_out.Close.assert_called_once()
    output.Close.assert_called_once()
    if fail_at != "input":
        input_handle.Close.assert_called_once()
        assert input_handle.SetConsoleMode.call_args.args == (7,)
