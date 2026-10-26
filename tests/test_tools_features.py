import json
from copy import deepcopy
from threading import Event
from unittest.mock import Mock

import pytest

from bruhanimate import (
    BackgroundPlayback,
    Buffer,
    CachedAnimation,
    CallbackEffect,
    EffectBrowser,
    EffectConfig,
    HistoryPlayback,
    MatrixSettings,
    SnowSettings,
    Tween,
    cli,
    get_theme,
)
from bruhanimate.bruhutil.bruhscreen import Screen


def test_saved_config_round_trip_and_protection(tmp_path):
    config = EffectConfig(
        "matrix",
        MatrixSettings(seed=7, character_halt_range=(2, 4)),
        fps=60,
        duration=2,
    )
    path = config.save(tmp_path / "matrix.json")
    assert EffectConfig.load(path) == config
    with pytest.raises(FileExistsError):
        config.save(path)
    config.fps = 24
    config.save(path, overwrite=True)
    assert EffectConfig.load(path).fps == 24


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"schema_version": 2},
        {"schema_version": True},
        {"schema_version": 1, "effect": "snow", "unknown": 0},
        {"schema_version": 1, "effect": "snow", "settings": {"wind": 10}},
        {"schema_version": 1, "effect": "snow", "fps": False},
    ],
)
def test_saved_config_rejects_invalid_data(tmp_path, data):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises((TypeError, ValueError)):
        EffectConfig.load(path)


def test_cli_saved_settings_and_explicit_overrides(tmp_path, monkeypatch):
    path = str(tmp_path / "snow.json")
    assert (
        cli.main(
            [
                "save-preset",
                "snow",
                path,
                "--preset",
                "light",
                "--seed",
                "7",
                "--fps",
                "60",
                "--frames",
                "9",
            ]
        )
        == 0
    )
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    cli.main(["play", "snow", "--config", path, "--set", "wind=0.4", "--frames", "2"])
    assert run.call_args.kwargs["fps"] == 60
    assert run.call_args.kwargs["frames"] == 2
    assert run.call_args.kwargs["settings"] == SnowSettings(
        intensity=0.005, seed=7, wind=0.4
    )
    with pytest.raises(SystemExit):
        cli.main(["play", "matrix", "--config", path])


def test_cli_export_routes_dimensions_font_and_protects_no_limit(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli, "export_animation", run)
    cli.main(
        [
            "export",
            "snow",
            str(tmp_path / "snow.mp4"),
            "--frames",
            "2",
            "--width",
            "20",
            "--font-size",
            "18",
        ]
    )
    assert run.call_args.kwargs["width"] == 20
    assert run.call_args.kwargs["height"] == 24
    assert run.call_args.kwargs["style"].font_size == 18


def test_tween_only_mutates_on_start_update_and_clamps_large_dt():
    values = []
    tween = Tween(values.append, 0, 10, duration=2, easing="ease_in")
    assert values == []
    tween.start()
    tween.update(1)
    assert values == [0, 2.5]
    tween.draw(Buffer(1, 1))
    assert values == [0, 2.5]
    tween.update(1e100)
    assert values[-1] == 10 and tween.finished
    tween.close()
    with pytest.raises(RuntimeError):
        tween.start()


def test_reversing_tween_and_repeat():
    tween = Tween(lambda value: None, 0, 10, duration=1, reverse=True)
    tween.start()
    tween.update(1.5)
    assert tween.value == 5
    tween.update(0.5)
    assert tween.value == 0 and tween.finished
    repeat = Tween(lambda value: None, 0, 10, duration=1, repeat=True)
    repeat.start()
    repeat.update(1000.5)
    assert repeat.value == 5 and not repeat.finished


def test_cache_invalidates_and_never_shares_presented_buffer():
    state = ["A"]
    calls = []

    def draw(buffer):
        calls.append(True)
        buffer.put_char(0, 0, state[0])

    child = CallbackEffect(draw)
    cache = CachedAnimation(child)
    cache.start()
    first = Buffer(1, 2).clear_buffer(val=".")
    cache.draw(first)
    state[0] = "B"
    cache.update(1)
    second = Buffer(1, 2).clear_buffer(val=".")
    cache.draw(second)
    assert first.buffer == second.buffer == [["A", "."]]
    assert len(calls) == 1
    cache.invalidate()
    cache.draw(second)
    assert first.buffer == [["A", "."]] and second.buffer == [["B", "."]]
    cache.resize((3, 1))
    cache.draw(Buffer(1, 3))
    assert len(calls) == 3
    cache.close()


def test_history_replay_does_not_consume_source_and_evicts_bookmarks():
    consumed = []

    def states():
        for i in range(5):
            consumed.append(i)
            yield i

    playback = HistoryPlayback(
        states(), lambda state, buffer: None, capacity=2, paused=True
    )
    playback.start()
    playback.step()
    playback.update(0)
    playback.bookmark("first")
    playback.step()
    playback.update(0)
    playback.back()
    assert playback.state == 1
    playback.update(0)
    assert playback.state == 0 and playback.paused
    playback.step()
    playback.update(0)
    assert playback.state == 1 and consumed == [0, 1]
    playback.step()
    playback.update(0)
    assert playback.history_start == 1 and playback.bookmarks == {}
    with pytest.raises(ValueError):
        playback.seek(0)
    playback.close()


def test_history_can_rewind_after_exhaustion_and_copies_mutable_snapshots():
    def states():
        state = []
        for i in range(2):
            state.append(i)
            yield state

    playback = HistoryPlayback(
        states(), lambda state, buffer: None, copy_state=deepcopy
    )
    playback.start()
    playback.update(0)
    playback.update(1)
    assert playback.finished
    playback.back()
    playback.update(0)
    assert playback.state == [0] and not playback.finished
    playback.step()
    playback.update(0)
    assert playback.state == [0, 1] and playback.finished
    playback.close()


def test_background_is_inert_and_manual_step_waits_for_snapshot():
    ready, release, closed = Event(), Event(), Event()

    def states(cancel):
        try:
            ready.set()
            assert release.wait(2)
            yield 7
        finally:
            closed.set()

    playback = BackgroundPlayback(states, lambda state, buffer: None, paused=True)
    assert not ready.is_set()
    playback.start()
    assert ready.wait(2)
    playback.step()
    playback.update(0)
    assert playback.steps == 0
    release.set()
    assert closed.wait(2)
    playback.update(0)
    assert playback.state == 7 and playback.steps == 1
    playback.close()
    assert not playback._thread.is_alive()


def test_background_cancels_full_queue_and_closes_on_worker():
    produced, closed = Event(), Event()

    def states(cancel):
        try:
            yield 1
            produced.set()
            yield 2
        finally:
            closed.set()

    playback = BackgroundPlayback(
        states, lambda state, buffer: None, capacity=1, paused=True
    )
    playback.start()
    assert produced.wait(2)
    playback.close()
    assert closed.is_set()
    playback.close()


def test_background_failure_and_retryable_shutdown():
    released, entered = Event(), Event()

    def states(cancel):
        entered.set()
        released.wait(2)
        raise ValueError("solver failed")
        yield

    playback = BackgroundPlayback(states, lambda state, buffer: None, close_timeout=0)
    playback.start()
    assert entered.wait(2)
    with pytest.raises(RuntimeError, match="did not stop"):
        playback.close()
    released.set()
    playback._thread.join(2)
    playback.close()
    broken = BackgroundPlayback(lambda cancel: iter(()), lambda state, buffer: None)
    broken._factory = lambda cancel: (_ for _ in ()).throw(ValueError("solver failed"))
    broken.start()
    broken._thread.join(2)
    try:
        with pytest.raises(ValueError, match="solver failed"):
            broken.update(0)
    finally:
        broken.close()


def test_browser_selection_is_deferred_and_resize_keeps_child():
    browser = EffectBrowser(size=(30, 12))
    assert browser._child is None
    assert "audio" not in browser.names and "terminal" not in browser.names
    browser.start()
    previous = browser._child
    browser.handle_event(Screen.KEY_DOWN)
    assert browser._child is previous
    browser.update(1 / 30)
    assert browser._child is not previous
    selected = browser._child
    browser.resize((40, 14))
    assert browser._child is selected
    browser.draw(Buffer(14, 40))
    assert "play(" in browser.command
    browser.close()
    browser.close()


def test_theme_palette_and_export_defaults_agree():
    theme = get_theme("high_contrast")
    assert theme.style("accent").foreground == theme.accent
    assert theme.export_style().background == (0, 0, 0)
    assert theme.export_style().foreground == (255, 255, 255)
    with pytest.raises(ValueError):
        get_theme("missing")


def test_browser_cli_prints_selected_code_after_restoring_player(monkeypatch, capsys):
    def play(**options):
        browser = options["effect_factory"](Buffer(10, 30))
        try:
            browser.start()
            browser.update(1 / 30)
            assert options["event_handler"](ord("q"))
        finally:
            browser.close()
        print("restored")

    monkeypatch.setattr(cli, "play", play)
    cli.main(["browse", "--frames", "1"])
    output = capsys.readouterr().out
    assert output.index("restored") < output.index("from bruhanimate import play")


def test_browser_and_cache_close_partial_startup_once(monkeypatch):
    from bruhanimate import effect_registry

    child = CallbackEffect(lambda buffer: None)
    monkeypatch.setattr(child, "start", Mock(side_effect=ValueError("startup")))
    monkeypatch.setattr(child, "close", Mock())
    monkeypatch.setattr(effect_registry, "create", Mock(return_value=child))
    browser = EffectBrowser()
    browser.start()
    assert browser.error == "ValueError: startup"
    assert not browser._closed
    browser.close()
    child.close.assert_called_once()
    child.close.reset_mock()
    cached = CachedAnimation(child)
    with pytest.raises(ValueError, match="startup"):
        cached.start()
    cached.close()
    child.close.assert_called_once()


def test_background_copy_happens_before_producer_mutates_and_cleanup_failure_surfaces():
    class Source:
        def __init__(self):
            self.value = []
            self.index = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.index == 2:
                raise StopIteration
            self.value.append(self.index)
            self.index += 1
            return self.value

        def close(self):
            raise ValueError("cleanup failed")

    playback = BackgroundPlayback(
        lambda cancel: Source(),
        lambda state, buffer: None,
        copy_state=deepcopy,
        capacity=4,
        paused=True,
    )
    playback.start()
    playback._thread.join(2)
    assert not playback._thread.is_alive()
    playback.step()
    playback.update(0)
    assert playback.state == [0]
    playback.step()
    playback.update(0)
    assert playback.state == [0, 1]
    with pytest.raises(ValueError, match="cleanup failed"):
        playback.close()
    playback.close()


def test_cli_real_export_is_headless_and_errors_do_not_replace_output(
    tmp_path, monkeypatch
):
    pytest.importorskip("PIL")
    monkeypatch.setattr(
        Screen, "open", Mock(side_effect=AssertionError("terminal opened"))
    )
    output = tmp_path / "snow.gif"
    command = [
        "export",
        "snow",
        str(output),
        "--frames",
        "2",
        "--width",
        "4",
        "--height",
        "2",
    ]
    assert cli.main(command) == 0
    original = output.read_bytes()
    assert original.startswith(b"GIF")
    with pytest.raises(SystemExit):
        cli.main(command)
    assert output.read_bytes() == original
    with pytest.raises(SystemExit):
        cli.main(["export", "snow", str(tmp_path / "bad.mp4")])
    assert not (tmp_path / "bad.mp4").exists()


def test_every_builtin_config_round_trips(tmp_path):
    from bruhanimate import effect_registry

    for name in effect_registry.names():
        cls = effect_registry.get(name).settings_cls
        config = EffectConfig(name, cls() if cls else None)
        assert EffectConfig.load(config.save(tmp_path / f"{name}.json")) == config
