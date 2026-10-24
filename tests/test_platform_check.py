"""Mocked platform-check control flow; real PTY execution is a separate CI step."""

import json
from unittest.mock import Mock

import pytest
from test_player import RecordingScreen

from scripts import check_platform


def test_default_report_does_not_open_devices(monkeypatch, capsys):
    terminal = Mock()
    audio = Mock()
    monkeypatch.setattr(check_platform, "terminal_check", terminal)
    monkeypatch.setattr(check_platform, "audio_check", audio)
    assert check_platform.main([]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["terminal"]["status"] == data["audio"]["status"] == "not_run"
    terminal.assert_not_called()
    audio.assert_not_called()


def test_terminal_requires_tty_before_open(monkeypatch):
    monkeypatch.setattr(check_platform.sys.stdin, "isatty", lambda: False)
    terminal = Mock()
    monkeypatch.setattr(check_platform, "terminal_check", terminal)
    with pytest.raises(SystemExit):
        check_platform.main(["--terminal"])
    terminal.assert_not_called()


def test_native_failure_still_restores_screen(monkeypatch):
    from bruhanimate import Screen

    screen = RecordingScreen()
    screen.flush_frame = Mock(side_effect=RuntimeError("write failed"))
    monkeypatch.setattr(Screen, "open", lambda: screen)
    with pytest.raises(RuntimeError):
        check_platform.terminal_check()
    assert screen.closed


def test_audio_inconclusive_is_not_reported_as_success(monkeypatch, capsys):
    monkeypatch.setattr(
        check_platform, "audio_check", lambda seconds: {"status": "inconclusive"}
    )
    assert check_platform.main(["--audio"]) == 1
    assert json.loads(capsys.readouterr().out)["audio"]["status"] == "inconclusive"


def test_failed_native_check_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(
        check_platform, "pty_check", Mock(side_effect=RuntimeError("failed probe"))
    )
    path = tmp_path / "report.json"
    assert check_platform.main(["--pty", "--output", str(path)]) == 1
    assert json.loads(path.read_text())["terminal"]["error"] == "failed probe"
