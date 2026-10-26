import builtins
import subprocess
import sys
from unittest.mock import Mock
from xml.etree import ElementTree as ET

import pytest

from bruhanimate import (
    CallbackEffect,
    ExportStyle,
    Frame,
    export_animation,
    save_png,
    save_svg,
)
from bruhanimate.export import _MP4, _cell, _Rasterizer


@pytest.mark.parametrize(
    "value,expected",
    [
        ("\x1b[31mX\x1b[0m", ((128, 0, 0), (1, 2, 3), False, False)),
        ("\x1b[38;5;0;48;5;255mX", ((0, 0, 0), (238, 238, 238), False, False)),
        ("\x1b[38;2;1;2;3;48:2::4:5:6;1;4mX", ((1, 2, 3), (4, 5, 6), True, True)),
        ("\x1b[38:2:1:2:3;0;1;22mX", ((200, 210, 220), (1, 2, 3), False, False)),
        ("\x1b[7mX", ((1, 2, 3), (200, 210, 220), False, False)),
        ("\x1b[2mX", ((100, 106, 111), (1, 2, 3), False, False)),
    ],
)
def test_ansi_color_resolution(value, expected):
    glyph, *style = _cell(value, (200, 210, 220), (1, 2, 3))
    assert glyph == "X" and tuple(style) == expected


@pytest.mark.parametrize(
    "value", ["\x1b[3mX", "\x1b[38;5;256mX", "\x1b[48;2;1mX", "\x1b[2JX", "XX", "界"]
)
def test_invalid_or_unsupported_cells_are_rejected(value, tmp_path):
    path = tmp_path / "bad.svg"
    with pytest.raises(ValueError):
        save_svg(Frame(0, 0, ((value,),)), path)
    assert not path.exists()


def test_svg_escapes_text_and_preserves_colors_without_optional_packages(tmp_path):
    frame = Frame(0, 0, (("<", "&", "\x1b[48;2;1;2;3m "),))
    path = save_svg(frame, tmp_path / "frame.svg")
    root = ET.parse(path).getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}
    assert root.attrib["width"] == "30"
    assert [n.text for n in root.findall(".//s:text", ns)] == ["<", "&"]
    assert root.findall("s:rect", ns)[-1].attrib["fill"] == "#010203"
    with pytest.raises(FileExistsError):
        save_svg(frame, path)
    save_svg(Frame(0, 0, (("B",),)), path, overwrite=True)
    assert ET.parse(path).getroot().attrib["width"] == "10"


def test_raster_png_background_and_cell_clipping(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    frame = Frame(0, 0, (("\x1b[48;2;1;2;3m ", "\x1b[48;5;196m "),))
    path = save_png(frame, tmp_path / "frame.png", style=ExportStyle(cell_size=(3, 5)))
    with Image.open(path) as image:
        assert image.size == (6, 5)
        assert image.getpixel((1, 2)) == (1, 2, 3)
        assert image.getpixel((4, 2)) == (255, 0, 0)
    path = save_png(
        Frame(0, 0, (("W", " "),)),
        tmp_path / "clip.png",
        style=ExportStyle(cell_size=(3, 5), font_size=40),
    )
    with Image.open(path) as image:
        assert all(
            image.getpixel((x, y)) == (12, 12, 12)
            for x in range(3, 6)
            for y in range(5)
        )


@pytest.mark.parametrize("bold", [False, True])
def test_raster_text_shares_baseline_and_preserves_descenders(bold):
    Image = pytest.importorskip("PIL.Image")
    ImageChops = pytest.importorskip("PIL.ImageChops")
    style = ExportStyle(cell_size=(24, 40), font_size=28)
    raster = _Rasterizer(style)
    bounds = {}
    try:
        for glyph in "He.gpy_":
            cell = f"\x1b[1m{glyph}" if bold else glyph
            tile = raster._tile(cell)
            with Image.new("RGB", tile.size, style.background) as background:
                difference = ImageChops.difference(tile, background)
                try:
                    bounds[glyph] = difference.getbbox()
                finally:
                    difference.close()
        assert all(bounds.values())
        # Capital, lowercase and punctuation sit on the same writing line.
        assert bounds["H"][3] == bounds["e"][3] == bounds["."][3]
        assert bounds["."][1] > bounds["e"][1] > bounds["H"][1]
        assert all(bounds[c][3] > bounds["e"][3] for c in "gpy_")
    finally:
        raster.close()


def test_gif_preserves_total_timing_and_closes_owned_content(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    tick = [0]

    def update(dt):
        tick[0] += 1

    effect = CallbackEffect(lambda b: b.clear_buffer(val=str(tick[0])), update=update)
    effect.close = Mock()
    path = tmp_path / "clip.gif"
    assert export_animation(path, effect, width=2, height=1, frames=3, fps=30) == 3
    effect.close.assert_called_once()
    with Image.open(path) as image:
        assert image.size == (20, 20)
        durations = []
        for i in range(image.n_frames):
            image.seek(i)
            durations.append(image.info["duration"])
        assert sum(durations) == 100
        assert image.info["loop"] == 0


def test_real_mp4_is_decodable_and_pads_odd_dimensions(tmp_path):
    pytest.importorskip("PIL")
    ffmpeg = pytest.importorskip("imageio_ffmpeg")
    path = tmp_path / "clip.mp4"
    assert (
        export_animation(
            path,
            "plasma",
            width=3,
            height=1,
            style=ExportStyle(cell_size=(3, 5)),
            frames=3,
            fps=10,
        )
        == 3
    )
    reader = ffmpeg.read_frames(str(path))
    try:
        metadata = next(reader)
        frames = list(reader)
        assert metadata["size"] == (10, 6)
        assert metadata["fps"] == 10
        assert len(frames) == 3 and len(frames[0]) == 10 * 6 * 3
    finally:
        reader.close()


def test_failed_render_preserves_existing_destination_and_cleans_temp(tmp_path):
    path = tmp_path / "clip.gif"
    path.write_bytes(b"original")
    effect = CallbackEffect(Mock(side_effect=RuntimeError("draw failed")))
    effect.close = Mock()
    with pytest.raises(RuntimeError, match="draw failed"):
        export_animation(path, effect, frames=2, overwrite=True)
    effect.close.assert_called_once()
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]


def test_gif_budget_and_zero_limits(tmp_path):
    pytest.importorskip("PIL")
    path = tmp_path / "clip.gif"
    effect = CallbackEffect(lambda b: b.clear_buffer(val="x"))
    effect.close = Mock()
    with pytest.raises(ValueError, match="gif_max_pixels"):
        export_animation(path, effect, width=1, height=1, frames=3, gif_max_pixels=400)
    assert not path.exists() and not list(tmp_path.iterdir())
    effect.close.assert_called_once()
    factory = Mock()
    assert export_animation(path, effect_factory=factory, frames=0) == 0
    assert not path.exists()
    factory.assert_not_called()


def test_missing_optional_dependency_is_actionable(monkeypatch, tmp_path):
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError("blocked")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    with pytest.raises(ImportError, match=r"bruhanimate\[export\]"):
        save_png(Frame(0, 0, (("x",),)), tmp_path / "x.png")
    assert not list(tmp_path.iterdir())


def test_import_does_not_load_optional_modules_or_launch_processes():
    script = "import sys, bruhanimate; assert 'PIL' not in sys.modules; assert 'imageio_ffmpeg' not in sys.modules"
    subprocess.run([sys.executable, "-I", "-c", script], check=True, timeout=10)


def test_encoder_nonzero_exit_and_timeout_are_errors_and_reaped(monkeypatch, tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    process = Mock()
    process.wait.return_value = 3
    process.poll.return_value = 3
    monkeypatch.setattr(
        "bruhanimate.export.subprocess.Popen", Mock(return_value=process)
    )
    encoder = _MP4(tmp_path / "x.mp4", (4, 4), 30)
    with pytest.raises(RuntimeError, match="failed"):
        encoder.close()
    assert encoder.error.closed
    encoder.close()
    process.wait.assert_called_once()
    process = Mock()
    process.wait.side_effect = [subprocess.TimeoutExpired("ffmpeg", 30), 0]
    process.poll.return_value = 0
    monkeypatch.setattr(
        "bruhanimate.export.subprocess.Popen", Mock(return_value=process)
    )
    encoder = _MP4(tmp_path / "x.mp4", (4, 4), 30)
    with pytest.raises(RuntimeError, match="30 seconds"):
        encoder.close()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2 and encoder.error.closed


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"format": "avi"}, ValueError),
        ({"fps": 0}, ValueError),
        ({"format": "gif", "fps": 120}, ValueError),
        ({"gif_max_pixels": 0}, ValueError),
        ({"style": "dark"}, TypeError),
        ({"overwrite": 1}, TypeError),
    ],
)
def test_export_validation_before_start(tmp_path, kwargs, error):
    factory = Mock()
    with pytest.raises(error):
        export_animation(tmp_path / "a.mp4", effect_factory=factory, frames=2, **kwargs)
    factory.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"cell_size": (0, 1)}, ValueError),
        ({"font_size": True}, TypeError),
        ({"foreground": (1, 2, 300)}, ValueError),
        ({"background": "black"}, TypeError),
    ],
)
def test_style_validation(kwargs, error):
    with pytest.raises(error):
        ExportStyle(**kwargs)


def test_destination_created_during_render_is_not_replaced(tmp_path):
    from bruhanimate.export import _output

    destination = tmp_path / "race.svg"
    with pytest.raises(FileExistsError):
        with _output(destination, False) as temporary:
            temporary.write_text("rendered", encoding="utf-8")
            destination.write_text("another writer", encoding="utf-8")
    assert destination.read_text(encoding="utf-8") == "another writer"
    assert list(tmp_path.iterdir()) == [destination]
