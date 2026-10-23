"""Smoke-test an installed distribution with python -I, outside editable imports."""

import contextlib
import io
import json
from importlib.metadata import distribution, version
from pathlib import Path


def main() -> None:
    import bruhanimate as package
    from bruhanimate import Buffer, Playback, SnowSettings, draw_grid, effects
    from bruhanimate.cli import main as cli_main

    source = Path(__file__).resolve().parents[1] / "bruhanimate"
    installed = Path(package.__file__).resolve()
    if installed.is_relative_to(source):
        raise RuntimeError(
            "Smoke test imported the checkout instead of the installed distribution"
        )
    assert version("bruhanimate") == package.__version__
    assert (installed.parent / "py.typed").is_file()
    assert all(hasattr(package, name) for name in package.__all__)
    assert effects.snow.preset("light") == SnowSettings(intensity=0.005)
    assert "snow" in effects.names()
    command = next(
        entry
        for entry in distribution("bruhanimate").entry_points
        if entry.group == "console_scripts" and entry.name == "bruhanimate"
    )
    assert command.load() is cli_main
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert command.load()(["presets", "snow"]) == 0
    assert "light" in output.getvalue() and "0.005" in output.getvalue()
    captured = []
    assert (
        effects.noise.capture(
            seed=42, on_frame=captured.append, frames=2, width=4, height=2
        )
        == 2
    )
    assert isinstance(captured[0], package.Frame)
    recording = io.StringIO()
    assert effects.noise.record(recording, seed=42, frames=2, width=4, height=2) == 2
    assert json.loads(recording.getvalue().splitlines()[0]) == {
        "version": 2,
        "width": 4,
        "height": 2,
    }
    buffer = Buffer(1, 2)
    assert "beam_demo" in package.__valid_demos__
    panels = []
    panel = package.Panel(
        effect_factory=lambda local: package.SnowEffect(
            local, " ", SnowSettings(seed=42)
        ),
        size=(4, 2),
        position=(1, 1),
        title="Snow",
        updates_per_second=15,
    )
    assert (
        package.capture(panel, on_frame=panels.append, frames=3, width=8, height=6) == 3
    )
    assert panel.outer_size == (6, 4)
    assert panels[-1].cells[1][1] == "+"
    layout = package.Column(
        package.Slot(package.Label("Ready", align="center")),
        package.Slot(package.StatusBar(right="q"), size=package.Fixed(1)),
    )
    dashboard = []
    assert (
        package.capture(
            effect_factory=layout.build,
            on_frame=dashboard.append,
            frames=1,
            width=7,
            height=2,
        )
        == 1
    )
    assert dashboard[0].cells[0] == tuple(" Ready ")
    assert dashboard[0].cells[1][-1] == "q"
    assert "dashboard_demo" in package.__valid_demos__
    target = package.FocusTarget(
        "test",
        package.KeyBindings(
            package.KeyBinding("space", lambda: None, description="pause")
        ),
    )
    focus = package.FocusGroup(target)
    panel = package.Panel(package.Label("ready"), size=(5, 1), focus=target)
    panel.start()
    try:
        assert focus.focused is target and focus.help_text() == "space pause"
        assert focus.dispatch(32) is package.EventResult.HANDLED
        assert not focus.handle_event(32) and focus.handle_event(ord("q"))
    finally:
        panel.close()
    assert focus.focused is None
    log = package.LogView(size=(4, 1), max_lines=2)
    log.append("one\ntwo\nlast")
    scroller = package.ScrollView(log, size=(4, 1), content_size=(4, 1))
    scroller.start()
    try:
        frame = Buffer(1, 4)
        scroller.draw(frame)
        assert frame.buffer[0] == list("last")
        assert log.lines == ("two", "last")
        log.bindings.handle_event(package.Screen.KEY_HOME)
        assert not log.follow_tail
    finally:
        scroller.close()
    resizable = package.Column(
        package.Slot(package.Label("Ready", align="right"))
    ).build(Buffer(1, 5))
    assert isinstance(resizable, package.Resizable)
    resizable.start()
    try:
        resizable.resize((8, 2))
        resized = Buffer(2, 8)
        resizable.draw(resized)
        assert resized.buffer[0] == list("   Ready")
    finally:
        resizable.close()
    overlay = package.TimedOverlay(package.ImageEffect("x"), duration=0)
    scene = package.Scene(
        package.Layer(overlay, region=(0, 0, 1, 1), updates_per_second=15)
    )
    assert (
        package.capture(scene, on_frame=lambda frame: None, frames=1, width=2, height=1)
        == 1
    )
    draw_grid(buffer, ["AB"])
    assert buffer.buffer == [["A", "B"]]
    playback = Playback([1, 2], lambda state, target: None)
    playback.start()
    try:
        playback.update(0)
        playback.update(0.1)
        assert playback.state == 2
        playback.update(0.1)
        assert playback.finished
    finally:
        playback.close()
    print(f"Installed bruhanimate {package.__version__} verified at {installed}")


if __name__ == "__main__":
    main()
