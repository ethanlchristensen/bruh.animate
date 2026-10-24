"""Single-cell styling shared by widgets and animation layers."""

import re
from dataclasses import dataclass

from .grid import _glyph

_SGR = re.compile(r"\x1b\[([0-9;:]*)m")


@dataclass(frozen=True)
class TextStyle:
    """Per-cell ANSI styling; palette colors are 0..255, or None for defaults.

    On a Layer, None colors and bold=False leave child attributes unchanged;
    explicit colors and bold=True override them. Widget behavior is unchanged.
    """

    foreground: int | None = None
    background: int | None = None
    bold: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("foreground", self.foreground),
            ("background", self.background),
        ):
            if value is not None:
                if type(value) is not int:
                    raise TypeError(f"{name} must be an integer or None")
                if not 0 <= value <= 255:
                    raise ValueError(f"{name} must be between 0 and 255")
        if type(self.bold) is not bool:
            raise TypeError("bold must be a bool")

    def _prefix(self) -> str:
        codes = ["1"] if self.bold else []
        if self.foreground is not None:
            codes.append(f"38;5;{self.foreground}")
        if self.background is not None:
            codes.append(f"48;5;{self.background}")
        return f"\x1b[{';'.join(codes)}m" if codes else ""

    def _cell(self, glyph: str) -> str:
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
    if preserve_background and (style is None or style.background is None):
        lower_prefix = "" if lower is None else _prefix_and_glyph(str(lower))[0]
        prefix += _background(lower_prefix)
    if style is not None:
        prefix += style._prefix()
    return f"{prefix}{glyph}\x1b[0m" if prefix else glyph
