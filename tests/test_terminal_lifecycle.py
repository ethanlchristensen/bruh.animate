import shlex
import subprocess
import sys
from io import StringIO
from unittest.mock import Mock

import pytest
from test_player import RecordingScreen

from bruhanimate import Buffer, Player, Scene, TerminalEffect


def test_terminal_input_routes_printable_quit_key_to_shell():
    screen = RecordingScreen(events=[ord("q"), None, 27])
    renderer = TerminalEffect(Buffer(3, 5))
    Player(
        screen, renderer, frames=3, fps=None, event_handler=renderer.handle_event
    ).run()
    assert renderer.current_input == "q"
    assert screen.batches == 1


def test_scene_closes_other_children_when_process_cleanup_fails(monkeypatch):
    from test_player import TrackingEffect

    effect = TrackingEffect(Buffer(3, 5))
    terminal = TerminalEffect(Buffer(3, 5))
    scene = Scene(effect, terminal)
    scene.start()
    monkeypatch.setattr(
        terminal, "_close_process", Mock(side_effect=RuntimeError("process failed"))
    )
    with pytest.raises(RuntimeError, match="process failed"):
        scene.close()
    assert effect.calls == ["start", "close"]
    assert not terminal._started


def test_owned_command_and_pipe_readers_are_reaped():
    renderer = TerminalEffect(Buffer(3, 5))
    command = [
        sys.executable,
        "-u",
        "-c",
        "import time; print('ready', flush=True); time.sleep(30)",
    ]
    renderer.current_input = (
        subprocess.list2cmdline(command)
        if sys.platform == "win32"
        else shlex.join(command)
    )
    try:
        renderer.execute_command()
        process = renderer.active_process
        assert process is not None, renderer.terminal_history
        text = ""
        while not text.endswith("ready\n"):
            text += renderer.output_queue.get(timeout=5)
        readers = list(renderer._reader_threads)
    finally:
        renderer.close()

    assert process.poll() is not None
    assert all(not reader.is_alive() for reader in readers)
    assert all(
        stream.closed for stream in (process.stdin, process.stdout, process.stderr)
    )
    renderer.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job ownership")
def test_owned_job_reaps_command_descendants():
    import win32api
    import win32con
    import win32event

    renderer = TerminalEffect(Buffer(3, 5))
    script = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print(child.pid, flush=True); time.sleep(30)"
    )
    renderer.current_input = subprocess.list2cmdline(
        [sys.executable, "-u", "-c", script]
    )
    handle = None
    try:
        renderer.execute_command()
        assert renderer.active_process is not None, renderer.terminal_history
        line = ""
        while not line.endswith("\n"):
            line += renderer.output_queue.get(timeout=5)
        handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, int(line.strip()))
        renderer.close()
        assert win32event.WaitForSingleObject(handle, 2000) == 0
    finally:
        renderer.close()
        if handle is not None:
            handle.Close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job ownership")
def test_command_that_exits_before_job_assignment_keeps_its_output(monkeypatch):
    import pywintypes
    import win32api

    process = Mock()
    process.poll.return_value = 0
    process.stdin = StringIO()
    process.stdout = StringIO("ready\n")
    process.stderr = StringIO()
    process.pid = 0
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(
        win32api,
        "OpenProcess",
        Mock(side_effect=pywintypes.error(87, "OpenProcess", "process exited")),
    )
    renderer = TerminalEffect(Buffer(3, 5))
    renderer.current_input = "echo ready"
    try:
        renderer.execute_command()
        assert renderer.active_process is process, renderer.terminal_history
        line = ""
        while not line.endswith("\n"):
            line += renderer.output_queue.get(timeout=1)
        assert line == "ready\n"
    finally:
        renderer.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job ownership")
def test_command_waits_for_job_assignment_and_stdin_survives_gate(
    monkeypatch, tmp_path
):
    import time

    import win32job

    marker = tmp_path / "started"
    original = win32job.AssignProcessToJobObject

    def delayed_assignment(job, handle):
        time.sleep(0.3)
        assert not marker.exists(), "Command ran before ownership was established"
        return original(job, handle)

    monkeypatch.setattr(win32job, "AssignProcessToJobObject", delayed_assignment)
    renderer = TerminalEffect(Buffer(3, 10))
    script = "from pathlib import Path; import sys; Path(sys.argv[1]).touch(); print(input(), flush=True)"
    renderer.current_input = subprocess.list2cmdline(
        [sys.executable, "-u", "-c", script, str(marker)]
    )
    # The gate must use the real interpreter, not a venv redirector that can
    # create a process before job assignment. The user's command stays intact.
    monkeypatch.setattr(sys, "executable", "must-not-launch-venv-redirector.exe")
    try:
        renderer.execute_command()
        assert renderer.active_process is not None, renderer.terminal_history
        renderer.current_input = "hello"
        renderer.execute_command()
        result = ""
        while not result.endswith("\n"):
            result += renderer.output_queue.get(timeout=5)
        assert result == "hello\n"
    finally:
        renderer.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job ownership")
def test_job_assignment_failure_never_runs_command(monkeypatch, tmp_path):
    import win32job

    marker = tmp_path / "must-not-exist"
    monkeypatch.setattr(
        win32job,
        "AssignProcessToJobObject",
        Mock(side_effect=OSError("job unavailable")),
    )
    renderer = TerminalEffect(Buffer(3, 10))
    renderer.current_input = subprocess.list2cmdline(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
        ]
    )
    try:
        renderer.execute_command()
        assert not marker.exists()
        assert renderer.active_process is None
        assert any("job unavailable" in line for line in renderer.terminal_history)
    finally:
        renderer.close()
