import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bruhanimate import AudioEffect, Buffer
from bruhanimate.bruheffect import audio_effect


def test_fresh_import_and_every_demo_are_inert():
    script = """
import importlib
import os
import sys
import threading
from unittest.mock import patch
with patch.object(os, 'system', side_effect=AssertionError('shell on import')), \\
     patch.object(threading.Thread, 'start', side_effect=AssertionError('thread on import')):
    import bruhanimate
    assert not any(name.startswith('bruhanimate.demos.') for name in sys.modules)
    assert 'sounddevice' not in sys.modules
    assert 'pyaudiowpatch' not in sys.modules
    for name in bruhanimate.__valid_demos__:
        assert getattr(bruhanimate, name) is importlib.import_module('bruhanimate.demos.' + name)
    importlib.import_module('bruhanimate.demos.terminal_demo')
    assert 'snow_demo' in dir(bruhanimate)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_audio_construction_and_close_without_start_open_no_resources(monkeypatch):
    start = Mock(side_effect=AssertionError("thread during construction"))
    monkeypatch.setattr(threading.Thread, "start", start)
    effect = AudioEffect(Buffer(3, 5), " ")
    effect.close()
    effect.close()
    start.assert_not_called()


def test_audio_start_stop_are_idempotent_and_join_the_worker(monkeypatch):
    started = threading.Event()

    def capture(effect):
        started.set()
        effect._stop_event.wait()

    monkeypatch.setattr(AudioEffect, "_capture_loop", capture)
    effect = AudioEffect(Buffer(3, 5), " ")
    try:
        effect.start()
        first = effect._thread
        assert started.wait(1)
        effect.start()
        assert effect._thread is first
        effect.close()
        assert not first.is_alive()
        effect.close()
        started.clear()
        effect.start()
        assert started.wait(1)
        assert effect._thread is not first
    finally:
        effect.close()


def test_audio_reports_a_stuck_worker_and_allows_another_close():
    effect = AudioEffect(Buffer(3, 5), " ")
    worker = Mock()
    worker.is_alive.return_value = True
    effect._thread = worker
    with pytest.raises(RuntimeError, match="did not stop"):
        effect.stop(timeout=0)
    worker.is_alive.return_value = False
    effect.close()
    assert effect._thread is None


def test_audio_thread_start_failure_can_be_closed(monkeypatch):
    monkeypatch.setattr(
        threading.Thread, "start", Mock(side_effect=RuntimeError("thread failed"))
    )
    effect = AudioEffect(Buffer(3, 5), " ")
    with pytest.raises(RuntimeError, match="thread failed"):
        effect.start()
    effect.close()
    assert not effect._running


@pytest.mark.parametrize(
    "stage", ["lookup", "missing_device", "open", "start", "stop", None]
)
def test_windows_audio_releases_resources_on_success_and_failures(monkeypatch, stage):
    effect = AudioEffect(Buffer(3, 5), " ")
    pa, stream = Mock(), Mock()
    pa.get_host_api_info_by_type.return_value = {"defaultOutputDevice": 0}
    pa.get_device_info_by_index.return_value = {"name": "Speakers"}
    pa.get_loopback_device_info_generator.return_value = [
        {"name": "Speakers [Loopback]", "index": 1}
    ]
    pa.open.return_value = stream
    if stage == "lookup":
        pa.get_host_api_info_by_type.side_effect = RuntimeError("lookup failed")
    elif stage == "missing_device":
        pa.get_loopback_device_info_generator.return_value = []
        pa.get_device_count.return_value = 0
    elif stage == "open":
        pa.open.side_effect = RuntimeError("open failed")
    elif stage == "start":
        stream.start_stream.side_effect = RuntimeError("start failed")
    elif stage == "stop":
        stream.stop_stream.side_effect = RuntimeError("stop failed")
    monkeypatch.setattr(audio_effect, "_HAS_PAW", True)
    monkeypatch.setattr(
        audio_effect,
        "_pa_mod",
        SimpleNamespace(
            PyAudio=lambda: pa,
            paWASAPI=1,
            paFloat32=2,
            paContinue=3,
        ),
    )

    effect._capture_windows()

    pa.terminate.assert_called_once()
    if stage in ("start", "stop", None):
        stream.close.assert_called_once()
        stream.stop_stream.assert_called_once()
    assert bool(effect._error) == (stage is not None)


@pytest.mark.parametrize("stage", ["lookup", "start", "stop", None])
def test_non_windows_audio_closes_streams_and_reports_errors(monkeypatch, stage):
    effect = AudioEffect(Buffer(3, 5), " ")
    sd, stream = Mock(), Mock()
    sd.query_devices.return_value = []
    sd.InputStream.return_value = stream
    if stage == "lookup":
        sd.query_devices.side_effect = RuntimeError("device query failed")
    elif stage == "start":
        stream.start.side_effect = RuntimeError("start failed")
    elif stage == "stop":
        stream.stop.side_effect = RuntimeError("stop failed")
    monkeypatch.setattr(audio_effect, "_HAS_SD", True)
    monkeypatch.setattr(audio_effect, "_sd", sd)

    effect._capture_linux()

    if stage != "lookup":
        stream.stop.assert_called_once()
        stream.close.assert_called_once()
    assert bool(effect._error) == (stage is not None)
