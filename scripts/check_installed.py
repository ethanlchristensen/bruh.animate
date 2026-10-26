"""Smoke-test an installed distribution with python -I, outside editable imports."""

import contextlib
import io
import json
from importlib.metadata import distribution, version
from pathlib import Path
from tempfile import TemporaryDirectory


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
    from bruhanimate.doctor import diagnose

    assert "packages" in diagnose()
    rgb = package.TextStyle(foreground="#010203", enabled=True)._cell("x")
    assert "38;2;1;2;3" in rgb
    assert package.get_theme("high_contrast").export_style().background == (0, 0, 0)
    values = []
    tween = package.Tween(values.append, 0, 1)
    tween.start()
    tween.update(1)
    assert values == [0, 1] and tween.finished
    tween.close()
    history = package.HistoryPlayback([1, 2], lambda state, target: None)
    history.start()
    try:
        history.update(0)
        history.update(0.1)
        history.back()
        history.update(0)
        assert history.state == 1 and history.position == 0
    finally:
        history.close()
    assert effects.snow.preset("light") == SnowSettings(intensity=0.005)
    assert "snow" in effects.names()
    for name in ("water", "smoke", "metaballs", "cloth", "terrain"):
        info = getattr(effects, name)
        assert info.presets()
        effect = package.effect_registry.create(name, Buffer(8, 16), " ", seed=42)
        effect.start()
        try:
            effect.update(1 / 30)
            effect.resize((20, 10))
            effect.draw(Buffer(10, 20))
        finally:
            effect.close()
    assert effects.diffusion.preset("organic").shading
    assert "nature_demo" in package.__valid_demos__
    assert (
        package.capture(
            effect_factory=package.nature_demo.build_scene,
            on_frame=lambda frame: None,
            frames=2,
            width=80,
            height=24,
        )
        == 2
    )
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
    with TemporaryDirectory() as directory:
        config = package.EffectConfig("snow", package.SnowSettings(seed=42))
        config_path = config.save(Path(directory) / "snow.json")
        assert package.EffectConfig.load(config_path) == config
        svg = package.save_svg(captured[0], Path(directory) / "frame.svg")
        assert "<svg" in svg.read_text(encoding="utf-8")
    assert "routing_demo" in package.__valid_demos__
    accents = package.Scene(
        package.PathEffect([(0, 0), (1, 0)], size=(2, 1), mode="trace"),
        package.PulseEffect((0, 0), size=(2, 1)),
        package.RippleEffect((1, 0), size=(2, 1), metric="manhattan"),
    )
    assert package.capture(accents, on_frame=lambda frame: None, frames=2) == 2
    recording = io.StringIO()
    assert effects.noise.record(recording, seed=42, frames=2, width=4, height=2) == 2
    assert json.loads(recording.getvalue().splitlines()[0]) == {
        "version": 2,
        "width": 4,
        "height": 2,
    }
    buffer = Buffer(1, 2)
    assert "beam_demo" in package.__valid_demos__
    assert "image_demo" in package.__valid_demos__
    for transition in (package.FocusImageEffect, package.DissolveImageEffect):
        image = transition("X", x=0, y=0, duration=1, seed=42)
        image.start()
        image.update(1)
        assert image.finished
        frame = Buffer(1, 1)
        image.draw(frame)
        assert frame.get_char(0, 0) == "X"
        image.close()
    sequence = package.AnimationSequence(
        package.SequenceStep(
            lambda: package.WipeImageEffect(
                "AB", x=0, y=0, duration=1, direction="right"
            ),
            duration=1,
            name="wipe",
        )
    )
    sequence.resize((2, 1))
    sequence.start()
    try:
        sequence.update(1)
        frame = Buffer(1, 2)
        sequence.draw(frame)
        assert sequence.finished and frame.buffer == [list("AB")]
    finally:
        sequence.close()
    resized_effect = package.DiffusionEffect(Buffer(2, 3), " ")
    resized_effect.resize((5, 4))
    resized_effect.update(0.1)
    resized_effect.draw(Buffer(4, 5))
    resized_effect.close()
    styled = package.Scene(
        package.Layer(
            package.ImageEffect("AB", x=0, y=0),
            mask=package.ImageMask("# ", x=0, y=0),
            style=package.TextStyle(foreground=231, enabled=True),
            preserve_background=True,
        )
    )
    styled.start()
    frame = Buffer(1, 2).clear_buffer(val=".")
    styled.draw(frame)
    assert "231mA" in frame.get_char(0, 0) and frame.get_char(1, 0) == "."
    styled.close()
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
