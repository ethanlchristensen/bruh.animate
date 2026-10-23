"""Smoke-test an installed distribution with python -I, outside editable imports."""

from importlib.metadata import version
from pathlib import Path


def main() -> None:
    import bruhanimate as package
    from bruhanimate import Buffer, Playback, draw_grid

    source = Path(__file__).resolve().parents[1] / "bruhanimate"
    installed = Path(package.__file__).resolve()
    if installed.is_relative_to(source):
        raise RuntimeError(
            "Smoke test imported the checkout instead of the installed distribution"
        )
    assert version("bruhanimate") == package.__version__
    assert (installed.parent / "py.typed").is_file()
    assert all(hasattr(package, name) for name in package.__all__)
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
