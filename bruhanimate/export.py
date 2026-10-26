"""SVG snapshots and optional raster/video export through headless capture."""

from __future__ import annotations

import math
import os
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryFile
from typing import Literal, cast
from xml.etree import ElementTree as ET

from .capture import Frame, _player
from .player import EffectFactory, EffectSource
from .resize import _size
from .styling import _SGR, _prefix_and_glyph

RGB = tuple[int, int, int]
ExportFormat = Literal["gif", "mp4"]


class ExportCancelled(RuntimeError):
    """Export stopped cooperatively; no partial destination was published."""


@dataclass(frozen=True)
class ExportProgress:
    """Rendered frames, optional frame upper bound and wall-clock seconds.

    remaining_seconds estimates rendering only, excluding final encoding.
    Finite content may finish before total_frames. Callbacks run synchronously.
    """

    frames: int
    total_frames: int | None
    elapsed_seconds: float
    remaining_seconds: float | None
    phase: Literal["render", "encode", "complete"]


def _rgb(value: RGB) -> RGB:
    if (
        not isinstance(value, tuple)
        or len(value) != 3
        or any(type(n) is not int for n in value)
    ):
        raise TypeError("RGB colors must be three-integer tuples")
    if any(not 0 <= n <= 255 for n in value):
        raise ValueError("RGB components must be between 0 and 255")
    return value


@dataclass(frozen=True)
class ExportStyle:
    """Pixel cell size, font and default RGB colors for exported terminal cells.

    Raster exports use Pillow's bundled font unless font names a local TrueType/
    OpenType file. Glyph advances are centered horizontally; every row uses a
    shared font baseline. Glyphs are clipped to their own cells; font_size
    is positive pixels. SVG uses the viewer's monospace font (no font embedding).
    Terminal theme colors are not read; ANSI palette colors use the xterm palette.
    """

    cell_size: tuple[int, int] = (10, 20)
    font_size: int = 16
    font: str | os.PathLike[str] | None = None
    foreground: RGB = (229, 229, 229)
    background: RGB = (12, 12, 12)

    def __post_init__(self) -> None:
        _size(self.cell_size)
        if type(self.font_size) is not int:
            raise TypeError("font_size must be an integer")
        if self.font_size < 1:
            raise ValueError("font_size must be positive")
        if self.font is not None and not isinstance(self.font, (str, os.PathLike)):
            raise TypeError("font must be a filesystem path or None")
        _rgb(self.foreground)
        _rgb(self.background)


_ANSI = (
    (0, 0, 0),
    (128, 0, 0),
    (0, 128, 0),
    (128, 128, 0),
    (0, 0, 128),
    (128, 0, 128),
    (0, 128, 128),
    (192, 192, 192),
    (128, 128, 128),
    (255, 0, 0),
    (0, 255, 0),
    (255, 255, 0),
    (0, 0, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
)


def _palette(index: int) -> RGB:
    if not 0 <= index <= 255:
        raise ValueError("ANSI palette index must be 0..255")
    if index < 16:
        return _ANSI[index]
    if index >= 232:
        value = 8 + (index - 232) * 10
        return value, value, value
    index -= 16
    levels = (0, 95, 135, 175, 215, 255)
    return levels[index // 36], levels[index // 6 % 6], levels[index % 6]


def _extended(parts: list[str]) -> RGB:
    if len(parts) == 2 and parts[0] == "5":
        return _palette(int(parts[1]))
    if parts and parts[0] == "2":
        values = parts[1:]
        if len(values) == 4 and values[0] in ("", "0"):
            values = values[1:]
        if len(values) == 3:
            return _rgb((int(values[0]), int(values[1]), int(values[2])))
    raise ValueError("Malformed ANSI extended color")


@lru_cache(maxsize=4096)
def _cell(
    value: str, foreground: RGB, background: RGB
) -> tuple[str, RGB, RGB, bool, bool]:
    prefix, glyph = _prefix_and_glyph(value)
    fg, bg = foreground, background
    bold = dim = underline = inverse = False
    for match in _SGR.finditer(prefix):
        parts = match.group(1).split(";")
        i = 0
        while i < len(parts):
            part = parts[i]
            fields = part.split(":")
            code = int(fields[0] or 0)
            if code in (38, 48):
                if len(fields) > 1:
                    color = _extended(fields[1:])
                else:
                    if i + 1 >= len(parts) or parts[i + 1] not in ("2", "5"):
                        raise ValueError("Malformed ANSI extended color")
                    count = 2 if parts[i + 1] == "5" else 4
                    color = _extended(parts[i + 1 : i + 1 + count])
                    i += count
                if code == 38:
                    fg = color
                else:
                    bg = color
            elif code == 0:
                fg, bg, bold, dim, underline, inverse = (
                    foreground,
                    background,
                    False,
                    False,
                    False,
                    False,
                )
            elif code in (1, 2, 4, 7, 22, 24, 27):
                if code == 1:
                    bold = True
                elif code == 2:
                    dim = True
                elif code == 4:
                    underline = True
                elif code == 7:
                    inverse = True
                elif code == 22:
                    bold = dim = False
                elif code == 24:
                    underline = False
                elif code == 27:
                    inverse = False
            elif code == 39:
                fg = foreground
            elif code == 49:
                bg = background
            elif 30 <= code <= 37:
                fg = _palette(code - 30)
            elif 90 <= code <= 97:
                fg = _palette(code - 90 + 8)
            elif 40 <= code <= 47:
                bg = _palette(code - 40)
            elif 100 <= code <= 107:
                bg = _palette(code - 100 + 8)
            else:
                raise ValueError(f"Unsupported export SGR code: {code}")
            i += 1
    if inverse:
        fg, bg = bg, fg
    if dim:
        fg = tuple((a + b) // 2 for a, b in zip(fg, bg))  # type: ignore[assignment]
    return glyph, fg, bg, bold, underline


def _dimensions(frame: Frame, style: ExportStyle) -> tuple[int, int]:
    if not isinstance(style, ExportStyle):
        raise TypeError("style must be ExportStyle")
    if (
        not frame.cells
        or not frame.width
        or any(len(row) != frame.width for row in frame.cells)
    ):
        raise ValueError("frame must be a non-empty rectangle")
    return frame.width * style.cell_size[0], frame.height * style.cell_size[1]


@contextmanager
def _output(path: str | os.PathLike[str], overwrite: bool) -> Iterator[Path]:
    if type(overwrite) is not bool:
        raise TypeError("overwrite must be a bool")
    destination = Path(path).absolute()
    if not overwrite and destination.exists():
        raise FileExistsError(destination)
    with NamedTemporaryFile(
        dir=destination.parent,
        prefix=".bruhanimate-",
        suffix=destination.suffix,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        yield temporary_path
        if overwrite:
            os.replace(temporary_path, destination)
        elif os.name == "nt":
            # Windows rename refuses an existing destination atomically and
            # works on filesystems where hard links are unavailable.
            os.rename(temporary_path, destination)
        else:
            # Same-directory hard link publishes atomically without replacing a
            # file another process created while rendering. No partial output.
            os.link(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def save_svg(
    frame: Frame,
    path: str | os.PathLike[str],
    *,
    style: ExportStyle = ExportStyle(),
    overwrite: bool = False,
) -> Path:
    """Save an immutable Frame as SVG using only the standard library.

    Colors, bold, dim, underline and inverse SGR are supported; other attributes
    raise ValueError. Single-cell glyph rules match GridViewport. A complete
    file is published atomically; existing paths require overwrite=True. The
    parent directory must exist. No animation, input, terminal or resources are
    acquired beyond the output file. Returns the destination Path.
    """
    width, height = _dimensions(frame, style)
    root = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width=str(width),
        height=str(height),
        viewBox=f"0 0 {width} {height}",
    )
    cw, ch = style.cell_size
    for y, row in enumerate(frame.cells):
        for x, value in enumerate(row):
            glyph, fg, bg, bold, underline = _cell(
                value, style.foreground, style.background
            )

            def color(rgb: RGB) -> str:
                return "#%02x%02x%02x" % rgb

            ET.SubElement(
                root,
                "rect",
                x=str(x * cw),
                y=str(y * ch),
                width=str(cw),
                height=str(ch),
                fill=color(bg),
            )
            if glyph != " ":
                # A nested viewport clips glyphs and does not let a large font
                # overwrite the neighboring terminal cell.
                box = ET.SubElement(
                    root,
                    "svg",
                    x=str(x * cw),
                    y=str(y * ch),
                    width=str(cw),
                    height=str(ch),
                    overflow="hidden",
                )
                node = ET.SubElement(
                    box,
                    "text",
                    x=str(cw / 2),
                    y=str(ch / 2),
                    fill=color(fg),
                    attrib={
                        "font-family": "monospace",
                        "font-size": str(style.font_size),
                        "text-anchor": "middle",
                        "dominant-baseline": "central",
                        "font-weight": "bold" if bold else "normal",
                        "text-decoration": "underline" if underline else "none",
                    },
                )
                node.text = glyph
    with _output(path, overwrite) as temporary:
        ET.ElementTree(root).write(temporary, encoding="utf-8", xml_declaration=True)
    return Path(path)


class _Rasterizer:
    def __init__(self, style: ExportStyle):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise ImportError(
                'Raster/video export requires pip install "bruhanimate[export]"'
            ) from exc
        self.Image, self.ImageDraw, self.style = Image, ImageDraw, style
        self.font = (
            ImageFont.truetype(os.fspath(style.font), style.font_size)
            if style.font is not None
            # Supplying size selects Pillow's scalable default font.
            else cast(
                ImageFont.FreeTypeFont, ImageFont.load_default(size=style.font_size)
            )
        )
        ascent, descent = self.font.getmetrics()
        # A terminal row has one baseline, including punctuation and descenders.
        self.baseline = (style.cell_size[1] - ascent - descent) // 2 + ascent
        self._tile = lru_cache(maxsize=4096)(self._make_tile)

    def _make_tile(self, value: str):
        glyph, fg, bg, bold, underline = _cell(
            value, self.style.foreground, self.style.background
        )
        cw, ch = self.style.cell_size
        tile = self.Image.new("RGB", (cw, ch), bg)
        draw = self.ImageDraw.Draw(tile)
        if glyph != " ":
            origin = ((cw - self.font.getlength(glyph)) / 2, self.baseline)
            draw.text(
                origin,
                glyph,
                font=self.font,
                anchor="ls",
                fill=fg,
                stroke_width=int(bold),
                stroke_fill=fg,
            )
        if underline:
            draw.line((0, ch - 2, cw - 1, ch - 2), fill=fg)
        return tile

    def render(self, frame: Frame):
        size = _dimensions(frame, self.style)
        image = self.Image.new("RGB", size, self.style.background)
        cw, ch = self.style.cell_size
        try:
            for y, row in enumerate(frame.cells):
                for x, value in enumerate(row):
                    image.paste(self._tile(value), (x * cw, y * ch))
        except BaseException:
            image.close()
            raise
        return image

    def close(self) -> None:
        self._tile.cache_clear()


def save_png(
    frame: Frame,
    path: str | os.PathLike[str],
    *,
    style: ExportStyle = ExportStyle(),
    overwrite: bool = False,
) -> Path:
    """Save one Frame as PNG; requires the optional export extra.

    See save_svg for supported SGR, validation and atomic/no-overwrite behavior.
    Font loading happens only during this call, never on package import.
    """
    _dimensions(frame, style)
    rasterizer = _Rasterizer(style)
    try:
        image = rasterizer.render(frame)
        try:
            with _output(path, overwrite) as temporary:
                image.save(temporary, format="PNG")
        finally:
            image.close()
    finally:
        rasterizer.close()
    return Path(path)


class _MP4:
    """One owned encoder process with bounded cleanup and checked exit status."""

    def __init__(self, path: Path, size: tuple[int, int], fps: float):
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError as exc:
            raise ImportError(
                'MP4 export requires pip install "bruhanimate[export]"'
            ) from exc
        self.closed = False
        command = [
            get_ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{size[0]}x{size[1]}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(path),
        ]
        self.error = TemporaryFile()
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self.error,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except BaseException:
            self.error.close()
            raise

    def write(self, data: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(data)

    def close(self, *, abort: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if abort and self.process.poll() is None:
                self.process.kill()
            try:
                assert self.process.stdin is not None
                self.process.stdin.close()
            except BrokenPipeError:
                pass
            try:
                code = self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                raise RuntimeError(
                    "MP4 encoder did not finish within 30 seconds"
                ) from None
            if code and not abort:
                self.error.seek(0)
                detail = self.error.read(8192).decode("utf-8", errors="replace")
                raise RuntimeError(f"MP4 encoder failed ({code}): {detail}")
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.error.close()


def export_animation(
    path: str | os.PathLike[str],
    effect: EffectSource | None = None,
    *,
    effect_factory: EffectFactory | None = None,
    format: ExportFormat | None = None,
    style: ExportStyle = ExportStyle(),
    width: int = 80,
    height: int = 24,
    fps: float = 30,
    updates_per_second: float | None = None,
    frames: int | None = None,
    duration: float | None = None,
    on_complete: Literal["hold", "exit"] = "exit",
    background: str = " ",
    settings: object | None = None,
    preset: str | None = None,
    seed: int | None = None,
    overwrite: bool = False,
    gif_max_pixels: int = 20_000_000,
    on_progress: Callable[[ExportProgress], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> int:
    """Render owned content to GIF or H.264 MP4 without opening a terminal.

    Requires the optional export extra. format defaults to the .gif/.mp4 suffix.
    Timing, finite frames/duration limits and ownership follow capture. Output
    contains no audio/input; N frames play for N/fps seconds. GIF rounds frame
    durations to 10ms and loops forever (fps must be <=100); MP4 streams frames to bundled FFmpeg,
    padding odd pixel dimensions by one black pixel for codec compatibility.

    GIF retains frames, bounded by gif_max_pixels across all RGB images; use MP4
    for longer clips. Zero frames writes no file and starts no content/encoder.
    Complete output is atomically published; failures clean temporary output and
    close owned content/encoder. Existing paths require overwrite=True. Parent
    directories must exist. Returned value is the number of captured frames.
    on_progress receives frame counts and wall-clock estimates after each frame
    and at encoding/completion. cancelled is checked before startup, between
    frames and around final encoding; True raises ExportCancelled. Blocking
    encoder operations cannot be interrupted by this callback. Ctrl+C also
    cleans up. Cancellation preserves any existing destination.
    """
    selected = format if format is not None else Path(path).suffix.lower().lstrip(".")
    if selected not in ("gif", "mp4"):
        raise ValueError("format must be 'gif' or 'mp4' (or use that filename suffix)")
    if not isinstance(style, ExportStyle):
        raise TypeError("style must be ExportStyle")
    if type(overwrite) is not bool:
        raise TypeError("overwrite must be a bool")
    if type(gif_max_pixels) is not int:
        raise TypeError("gif_max_pixels must be an integer")
    if gif_max_pixels < 1:
        raise ValueError("gif_max_pixels must be positive")
    if on_progress is not None and not callable(on_progress):
        raise TypeError("on_progress must be callable")
    if cancelled is not None and not callable(cancelled):
        raise TypeError("cancelled must be callable")
    started = time.monotonic()
    rendered = 0
    total: int | None = None

    def check_cancel() -> None:
        if cancelled is not None and cancelled():
            raise ExportCancelled("Export cancelled")

    def report(phase: Literal["render", "encode", "complete"]) -> None:
        elapsed = max(0.0, time.monotonic() - started)
        remaining = (
            max(0, total - rendered) * elapsed / rendered
            if total is not None and rendered and phase == "render"
            else None
        )
        if on_progress is not None:
            on_progress(ExportProgress(rendered, total, elapsed, remaining, phase))

    check_cancel()
    images: list = []
    delays: list[int] = []
    rasterizer: _Rasterizer | None = None
    encoder: _MP4 | None = None
    temporary: Path

    def consume(frame: Frame) -> None:
        nonlocal rasterizer, encoder, rendered
        check_cancel()
        if (
            selected == "gif"
            and (len(images) + 1)
            * width
            * height
            * style.cell_size[0]
            * style.cell_size[1]
            > gif_max_pixels
        ):
            raise ValueError(
                "GIF exceeds gif_max_pixels; shorten the clip, reduce size, or use MP4"
            )
        if rasterizer is None:
            rasterizer = _Rasterizer(style)
        image = rasterizer.render(frame)
        if selected == "gif":
            images.append(image)
            i = len(images)
            delays.append(
                max(10, (round(i * 100 / fps) - round((i - 1) * 100 / fps)) * 10)
            )
        else:
            try:
                if encoder is None:
                    encoder = _MP4(temporary, image.size, fps)
                encoder.write(image.tobytes())
            finally:
                image.close()
        rendered += 1
        report("render")
        check_cancel()

    player = _player(
        effect,
        consume,
        effect_factory=effect_factory,
        width=width,
        height=height,
        fps=fps,
        updates_per_second=updates_per_second,
        frames=frames,
        duration=duration,
        on_complete=on_complete,
        background=background,
        settings=settings,
        preset=preset,
        seed=seed,
    )
    if selected == "gif" and fps > 100:
        raise ValueError("GIF fps must not exceed 100; use MP4 for higher rates")
    limits = [
        limit
        for limit in (
            frames,
            math.ceil(duration * fps) if duration is not None else None,
        )
        if limit is not None
    ]
    total = min(limits) if limits else None
    if player.frames == 0 or duration == 0:
        return 0
    try:
        with _output(path, overwrite) as temporary:
            count = player.run()
            if player.interrupted:
                raise ExportCancelled("Export interrupted")
            check_cancel()
            report("encode")
            check_cancel()
            if encoder is not None:
                encoder.close()
            if images:
                images[0].save(
                    temporary,
                    format="GIF",
                    save_all=True,
                    append_images=images[1:],
                    duration=delays,
                    loop=0,
                    disposal=2,
                    optimize=False,
                )
            if not count or temporary.stat().st_size == 0:
                raise RuntimeError("Export produced no frames")
            check_cancel()
            report("complete")
            check_cancel()
        return count
    finally:
        if encoder is not None:
            encoder.close(abort=True)
        for image in images:
            image.close()
        if rasterizer is not None:
            rasterizer.close()
