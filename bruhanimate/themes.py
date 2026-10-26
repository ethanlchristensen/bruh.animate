"""Named ANSI palettes shared by widgets, panels, effects and exports."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from .export import ExportStyle, _palette
from .styling import TextStyle

ThemeName = Literal["dark", "light", "high_contrast"]
ThemeRole = Literal["normal", "muted", "accent", "success", "warning", "error"]


class _PanelOptions(TypedDict):
    border_color: int
    border_background: int
    focus_border_color: int
    background: str


@dataclass(frozen=True)
class Theme:
    """Immutable semantic palette using xterm indexes 0..255.

    style supplies widget/Layer colors; palette supplies six indexes for effects
    accepting palettes. panel_options configures a Panel border/background.
    export_style uses the same default foreground/background, with the fixed
    xterm RGB mapping (it does not read a terminal's customized color table).
    Effects keep their own color APIs; applying a Theme never mutates children.
    """

    foreground: int = 252
    background: int = 234
    muted: int = 245
    accent: int = 81
    success: int = 114
    warning: int = 221
    error: int = 203

    def __post_init__(self) -> None:
        for color in (*self.palette, self.background):
            if type(color) is not int:
                raise TypeError("Theme colors must be integer palette indexes")
            TextStyle(foreground=color)

    @property
    def palette(self) -> tuple[int, ...]:
        return (
            self.foreground,
            self.muted,
            self.accent,
            self.success,
            self.warning,
            self.error,
        )

    def style(self, role: ThemeRole = "normal", *, bold: bool = False) -> TextStyle:
        if role not in ("normal", "muted", "accent", "success", "warning", "error"):
            raise ValueError("Unknown theme role")
        color = self.foreground if role == "normal" else getattr(self, role)
        return TextStyle(color, self.background, bold)

    def panel_options(self) -> _PanelOptions:
        return {
            "border_color": self.accent,
            "border_background": self.background,
            "focus_border_color": self.warning,
            "background": self.style()._cell(" "),
        }

    def export_style(
        self,
        *,
        font: str | None = None,
        font_size: int = 16,
        cell_size: tuple[int, int] = (10, 20),
    ) -> ExportStyle:
        return ExportStyle(
            font=font,
            font_size=font_size,
            cell_size=cell_size,
            foreground=_palette(self.foreground),
            background=_palette(self.background),
        )


def get_theme(name: ThemeName = "dark") -> Theme:
    """Return a named immutable theme; no global color state is changed."""
    themes = {
        "dark": Theme(),
        "light": Theme(234, 255, 240, 25, 28, 130, 160),
        "high_contrast": Theme(231, 16, 250, 51, 46, 226, 196),
    }
    if name not in themes:
        raise ValueError(f"Unknown theme: {name}")
    return themes[name]
