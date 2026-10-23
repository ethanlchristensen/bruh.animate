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
