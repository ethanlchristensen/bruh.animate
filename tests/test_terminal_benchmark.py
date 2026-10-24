"""Mocked benchmark contracts; these tests make no native-terminal claims."""

import json
from unittest.mock import Mock

import pytest
from test_player import RecordingScreen

from bruhanimate import AudioEffect, CallbackEffect
from scripts import benchmark_terminal
from scripts.benchmark_rendering import measure


def test_measure_uses_supplied_screen_and_closes_animation_on_failure():
    screen = RecordingScreen()
    animation = CallbackEffect(lambda b: b.clear_buffer(val="x"))
    animation.close = Mock()
    result = measure(
        "test", lambda b: animation, (5, 3), warmup=1, samples=2, screen=screen
    )
    assert screen.batches == 3 and not screen.closed
    assert result["mean_output_bytes"] is None
    animation.close.assert_called_once()
    screen.resized = True
    animation.close.reset_mock()
    with pytest.raises(RuntimeError, match="resized"):
        measure("test", lambda b: animation, (5, 3), warmup=0, samples=1, screen=screen)
    animation.close.assert_called_once()


def test_cpu_measure_still_reports_formatter_bytes():
    result = measure(
        "test",
        lambda b: CallbackEffect(lambda b: b.clear_buffer(val="x")),
        (5, 3),
        warmup=0,
        samples=1,
    )
    assert result["mean_output_bytes"] > 0


def test_native_guard_refuses_redirected_output_before_open(monkeypatch):
    monkeypatch.setattr(benchmark_terminal.sys.stdin, "isatty", lambda: False)
    opened = Mock()
    monkeypatch.setattr(benchmark_terminal.Screen, "open", opened)
    with pytest.raises(SystemExit):
        benchmark_terminal.main([])
    opened.assert_not_called()


@pytest.mark.parametrize("effect", ["plasma", "four_windows"])
def test_native_command_restores_screen_and_writes_metadata(
    monkeypatch, tmp_path, effect
):
    monkeypatch.setattr(
        AudioEffect, "start", lambda self: pytest.fail("benchmark opened audio")
    )
    screen = RecordingScreen()
    monkeypatch.setattr(benchmark_terminal.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(benchmark_terminal.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(benchmark_terminal.Screen, "open", lambda: screen)
    destination = tmp_path / "result.json"
    assert (
        benchmark_terminal.main(
            [
                "--effect",
                effect,
                "--samples",
                "2",
                "--warmup",
                "0",
                "--output",
                str(destination),
            ]
        )
        == 0
    )
    assert screen.closed and screen.batches == 2
    result = json.loads(destination.read_text())
    assert result["paced"] is False and result["results"][0]["size"] == [5, 3]
    assert "native" in result["backend"]


def test_native_command_restores_screen_after_present_failure(monkeypatch):
    screen = RecordingScreen()
    screen.flush_frame = Mock(side_effect=RuntimeError("write failed"))
    monkeypatch.setattr(benchmark_terminal.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(benchmark_terminal.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(benchmark_terminal.Screen, "open", lambda: screen)
    with pytest.raises(RuntimeError, match="write failed"):
        benchmark_terminal.main(["--samples", "1", "--warmup", "0"])
    assert screen.closed
