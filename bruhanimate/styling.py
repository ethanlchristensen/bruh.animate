"""Single-cell styling shared by widgets and animation layers."""

import os
import re
from dataclasses import dataclass

from .grid import _glyph

_SGR = re.compile(r"\x1b\[([0-9;:]*)m")
Color = int | str | tuple[int, int, int]


def _color_code(value: Color, channel: int) -> str:
    if isinstance(value, str):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Hex colors must be #RRGGBB")
        value = (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    if isinstance(value, tuple):
        if len(value) != 3 or any(
            type(part) is not int or not 0 <= part <= 255 for part in value
        ):
            raise ValueError("RGB colors require three integer channels in 0..255")
        return f"{channel};2;{value[0]};{value[1]};{value[2]}"
    if type(value) is not int:
        raise TypeError("Color must be a palette index, #RRGGBB or RGB tuple")
    if not 0 <= value <= 255:
        raise ValueError("Palette colors must be between 0 and 255")
    return f"{channel};5;{value}"


@dataclass(frozen=True)
class TextStyle:
    """Per-cell ANSI styling: 0..255, #RRGGBB, RGB tuples or None for defaults.

    On a Layer, None colors and bold=False leave child attributes unchanged;
    explicit colors and bold=True override them. Widget behavior is unchanged.
    enabled overrides color policy; None honors ANSI_COLORS_DISABLED and nonempty
    NO_COLOR. Explicit False also strips child SGR when used on a Layer.
    """

    foreground: Color | None = None
    background: Color | None = None
    bold: bool = False
    enabled: bool | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("foreground", self.foreground),
            ("background", self.background),
        ):
            if value is not None:
                _color_code(value, 38 if name == "foreground" else 48)
        if type(self.bold) is not bool:
            raise TypeError("bold must be a bool")
        if self.enabled is not None and type(self.enabled) is not bool:
            raise TypeError("enabled must be bool or None")

    def _enabled(self) -> bool:
        return (
            self.enabled
            if self.enabled is not None
            else not (
                "ANSI_COLORS_DISABLED" in os.environ or bool(os.getenv("NO_COLOR"))
            )
        )

    def _prefix(self) -> str:
        if not self._enabled():
            return ""
        codes = ["1"] if self.bold else []
        if self.foreground is not None:
            codes.append(_color_code(self.foreground, 38))
        if self.background is not None:
            codes.append(_color_code(self.background, 48))
        return f"\x1b[{';'.join(codes)}m" if codes else ""

    def _cell(self, glyph: str) -> str:
        if not self._enabled():
            return _SGR.sub("", glyph)
        prefix = self._prefix()
        return f"{prefix}{glyph}\x1b[0m" if prefix else glyph


def _background(prefix: str) -> str:
    """Resolve background at the glyph, including resets and RGB/palette SGR."""
    background = "\x1b[49m"
    for match in _SGR.finditer(prefix):
        parts = match.group(1).split(";")
        index = 0
        while index < len(parts):
            part = parts[index]
            if ":" in part:
                code = int(part.split(":", 1)[0] or 0)
                if code == 48:
                    background = f"\x1b[{part}m"
            else:
                code = int(part or 0)
                if code in (38, 48, 58) and index + 1 < len(parts):
                    length = {"5": 3, "2": 5}.get(parts[index + 1], 1)
                    if code == 48 and index + length <= len(parts):
                        background = f"\x1b[{';'.join(parts[index : index + length])}m"
                    index += length
                    continue
                if code in (0, 49):
                    background = "\x1b[49m"
                elif 40 <= code <= 47 or 100 <= code <= 107:
                    background = f"\x1b[{code}m"
            index += 1
    return background


def _prefix_and_glyph(value: str) -> tuple[str, str]:
    _glyph(value)
    end = 0
    while match := _SGR.match(value, end):
        end = match.end()
    return value[:end], value[end]


def _style_cell(
    value: str, lower: object, style: TextStyle | None, preserve_background: bool
) -> str:
    prefix, glyph = _prefix_and_glyph(value)
    if style is not None and not style._enabled():
        return glyph
    if preserve_background and (style is None or style.background is None):
        lower_prefix = "" if lower is None else _prefix_and_glyph(str(lower))[0]
        prefix += _background(lower_prefix)
    if style is not None:
        prefix += style._prefix()
    return f"{prefix}{glyph}\x1b[0m" if prefix else glyph
