import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bruhanimate.bruhutil import bruhscreen


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
