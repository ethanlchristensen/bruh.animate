import json
from unittest.mock import Mock

import pytest

from bruhanimate import (
    Buffer,
    CallbackEffect,
    EffectBrowser,
    EffectConfig,
    ExportCancelled,
    ExportStyle,
    TextStyle,
    cli,
    export_animation,
)
from bruhanimate.bruhutil.bruhscreen import Screen
from bruhanimate.export import _cell
from scripts.ci_scope import scope


def enter(browser, text):
    for character in text:
        assert not browser.handle_event(ord(character))
    assert not browser.handle_event(13)


def test_browser_search_edit_save_and_export_snapshot(tmp_path):
    browser = EffectBrowser(size=(30, 12), output_dir=tmp_path)
    browser.start()
    try:
        browser.handle_event(ord("/"))
        enter(browser, "snow")
        browser.update(0)
        assert browser.names == ("snow",)
        browser.handle_event(ord("e"))
        browser.handle_event(21)
        enter(browser, "wind=0.6")
        old = browser._child
        browser.update(0)
        assert browser._child is not old
        assert browser.configuration().settings.wind == 0.6
        assert "wind=0.6" in browser.command
        browser.handle_event(ord("s"))
        assert not list(tmp_path.iterdir())
        browser.update(0)
        path = tmp_path / "preview-snow-custom.json"
        assert EffectConfig.load(path).settings.wind == 0.6
        saved = path.read_bytes()
        browser.handle_event(ord("s"))
        browser.update(0)
        assert path.read_bytes() == saved and browser.message
        assert browser.handle_event(ord("x"))
        assert browser.export_request.settings.wind == 0.6
        assert browser.export_request.duration == 5
    finally:
        browser.close()


def test_browser_no_matches_categories_and_invalid_edit_are_recoverable():
    browser = EffectBrowser()
    browser.start()
    try:
        browser.filter("not-a-real-effect")
        browser.update(0)
        assert browser._child is None and browser.names == ()
        browser.draw(Buffer(3, 5))
        assert "No matching" in browser.command
        browser.filter("snow", "nature")
        browser.update(0)
        old = browser._child
        browser.handle_event(ord("e"))
        browser.handle_event(21)
        enter(browser, 'wind="bad"')
        browser.update(0)
        assert browser._child is old and "wind" in browser.message
        browser.handle_event(ord("c"))
        browser.update(0)
        assert browser.category != "nature"
    finally:
        browser.close()


@pytest.mark.parametrize("failure", ["start", "update", "resize"])
def test_browser_effect_error_closes_once_and_navigation_recovers(monkeypatch, failure):
    from bruhanimate import effect_registry

    broken = Mock()
    broken.resize = Mock()
    getattr(broken, failure).side_effect = RuntimeError("device unavailable")
    working = Mock()
    monkeypatch.setattr(effect_registry, "create", Mock(side_effect=[broken, working]))
    browser = EffectBrowser()
    browser.start()
    if failure == "update":
        browser.update(0)
    elif failure == "resize":
        browser.resize((50, 20))
    assert "device unavailable" in browser.error
    broken.close.assert_called_once()
    frame = Buffer(10, 60)
    browser.draw(frame)
    browser.handle_event(Screen.KEY_DOWN)
    browser.update(0)
    assert browser.error is None and browser._child is working
    browser.close()
    working.close.assert_called_once()


def test_browser_exports_after_terminal_restored(monkeypatch, tmp_path):
    restored = []

    def play(**options):
        browser = options["effect_factory"](Buffer(12, 30))
        browser.start()
        try:
            assert browser.handle_event(ord("x"))
        finally:
            browser.close()
        restored.append(True)

    def export(path, effect, **options):
        assert restored == [True]
        assert path.parent == tmp_path and options["duration"] == 2

    monkeypatch.setattr(cli, "play", play)
    monkeypatch.setattr(cli, "export_animation", export)
    assert (
        cli.main(["browse", "--output-dir", str(tmp_path), "--export-duration", "2"])
        == 0
    )


@pytest.mark.parametrize("format", ["gif", "mp4"])
def test_export_cancellation_preserves_destination_and_closes_content(tmp_path, format):
    pytest.importorskip("PIL")
    if format == "mp4":
        pytest.importorskip("imageio_ffmpeg")
    path = tmp_path / f"existing.{format}"
    path.write_bytes(b"original")
    content = CallbackEffect(lambda buffer: buffer.put_at(0, 0, "x"))
    original_close = content.close
    content.close = Mock(wraps=original_close)
    progress = []
    with pytest.raises(ExportCancelled):
        export_animation(
            path,
            content,
            width=2,
            height=2,
            frames=5,
            style=ExportStyle(cell_size=(8, 8)),
            overwrite=True,
            on_progress=progress.append,
            cancelled=lambda: len(progress) >= 2,
        )
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]
    content.close.assert_called_once()
    assert [state.frames for state in progress] == [1, 2]
    assert all(state.total_frames == 5 for state in progress)


def test_export_progress_completion_eta_and_callback_error(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from bruhanimate import export as module

    tick = iter(range(100))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(tick))
    progress = []
    path = tmp_path / "ok.gif"
    assert (
        export_animation(
            path, "static", width=2, height=2, frames=3, on_progress=progress.append
        )
        == 3
    )
    assert [state.phase for state in progress] == ["render"] * 3 + [
        "encode",
        "complete",
    ]
    assert [state.remaining_seconds for state in progress[:3]] == [2, 1, 0]

    def broken(state):
        raise ValueError("callback failed")

    data = path.read_bytes()
    with pytest.raises(ValueError, match="callback failed"):
        export_animation(
            path,
            "static",
            width=2,
            height=2,
            frames=2,
            overwrite=True,
            on_progress=broken,
        )
    assert path.read_bytes() == data and len(list(tmp_path.iterdir())) == 1


def test_cli_progress_and_ctrl_c(monkeypatch, tmp_path, capsys):
    from bruhanimate import ExportProgress

    def cancelled(*args, **options):
        options["on_progress"](ExportProgress(1, 5, 1, 4, "render"))
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "export_animation", cancelled)
    assert (
        cli.main(
            ["export", "snow", str(tmp_path / "x.gif"), "--frames", "5", "--progress"]
        )
        == 130
    )
    assert "1/5 frames" in capsys.readouterr().err


def test_doctor_is_read_only_and_reports_missing_optional_tools(monkeypatch, capsys):
    import subprocess

    from bruhanimate import doctor

    monkeypatch.setattr(
        subprocess, "Popen", Mock(side_effect=AssertionError("process opened"))
    )
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["color"] == "disabled"
    assert not any(report["available"].values())
    assert any("bruhanimate[export]" in message for message in report["advice"])
    assert "no terminal" in report["limits"].lower()


@pytest.mark.parametrize("color", ["#01aBff", (1, 171, 255)])
def test_rgb_style_reaches_export_unchanged(color):
    style = TextStyle(foreground=color, background="#090807", enabled=True)
    glyph, fg, bg, _, _ = _cell(style._cell("X"), (0, 0, 0), (0, 0, 0))
    assert (glyph, fg, bg) == ("X", (1, 171, 255), (9, 8, 7))


def test_color_controls_and_invalid_rgb(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert TextStyle(foreground=1)._cell("x") == "x"
    assert "\x1b[" in TextStyle(foreground=1, enabled=True)._cell("x")
    assert TextStyle(enabled=False)._cell("\x1b[31mx\x1b[0m") == "x"
    for invalid in ("#xyzxyz", (1, 2), (1, True, 3), (1, 2, 256)):
        with pytest.raises(ValueError):
            TextStyle(foreground=invalid)


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["README.md", "docs/source/index.rst"], (False, True)),
        (["tests/test_player.py"], (True, False)),
        (["bruhanimate/player.py"], (True, True)),
        ([".github/workflows/release.yml"], (True, True)),
        (["uv.lock"], (True, True)),
        (["unknown"], (True, True)),
        (["docs/file.rst", "tests/test_cli.py"], (True, True)),
    ],
)
def test_ci_scope(paths, expected):
    assert scope(paths) == expected


@pytest.mark.parametrize(
    "force,event,expected",
    [
        ("true", {"before": "1" * 40, "after": "2" * 40}, "full=true\ndocs=true\n"),
        ("false", {"before": "0" * 40, "after": "2" * 40}, "full=true\ndocs=true\n"),
        ("false", {"before": "1" * 40, "after": "2" * 40}, "full=false\ndocs=true\n"),
        (
            "false",
            {"pull_request": {"base": {"sha": "1" * 40}, "head": {"sha": "2" * 40}}},
            "full=false\ndocs=true\n",
        ),
    ],
)
def test_ci_event_selection_is_safe_and_release_always_full(
    tmp_path, monkeypatch, force, event, expected
):
    from scripts import ci_scope

    event_path, output = tmp_path / "event.json", tmp_path / "output"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("CI_FULL", force)
    git = Mock(return_value=Mock(stdout=b"README.md\x00"))
    monkeypatch.setattr(ci_scope.subprocess, "run", git)
    ci_scope.main()
    assert output.read_text() == expected
    if force == "true" or event.get("before") == "0" * 40:
        git.assert_not_called()
    else:
        assert git.call_args.args[0][:4] == ["git", "diff", "--name-only", "-z"]
        assert git.call_args.kwargs["check"] is True


@pytest.mark.parametrize("when", ["render", "encode", "complete"])
def test_interrupt_during_export_never_publishes_partial_output(tmp_path, when):
    pytest.importorskip("PIL")
    path = tmp_path / "preserve.gif"
    path.write_bytes(b"original")

    def interrupt(progress):
        if progress.phase == when:
            raise KeyboardInterrupt

    error = ExportCancelled if when == "render" else KeyboardInterrupt
    with pytest.raises(error):
        export_animation(
            path,
            "snow",
            width=2,
            height=2,
            frames=3,
            overwrite=True,
            on_progress=interrupt,
        )
    assert path.read_bytes() == b"original" and list(tmp_path.iterdir()) == [path]


def test_export_cancels_if_complete_callback_sets_flag(tmp_path):
    pytest.importorskip("PIL")
    cancel = [False]

    def progress(state):
        cancel[0] = state.phase == "complete"

    path = tmp_path / "cancelled.gif"
    with pytest.raises(ExportCancelled):
        export_animation(
            path,
            "snow",
            width=2,
            height=2,
            frames=2,
            on_progress=progress,
            cancelled=lambda: cancel[0],
        )
    assert not path.exists() and not list(tmp_path.iterdir())
