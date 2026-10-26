"""Interactive discovery, settings and saved presets using one Player."""

import json
import re
from copy import deepcopy
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

from ._validation import _seconds
from .bruheffect.registry import effect_registry
from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen
from .config import EffectConfig, resolve_overrides
from .player import Animation
from .resize import _resize, _size
from .themes import Theme, get_theme

_GROUPS = {
    "nature": {
        "snow",
        "rain",
        "fire",
        "water",
        "smoke",
        "terrain",
        "stars",
        "twinkle",
        "firework",
    },
    "simulation": {
        "boids",
        "game_of_life",
        "automaton",
        "diffusion",
        "cloth",
        "sand",
        "metaballs",
    },
    "patterns": {
        "plasma",
        "noise",
        "perlin",
        "matrix",
        "julia",
        "voronoi",
        "ripple",
        "draw_lines",
    },
    "audio": {"audio"},
}


def _category(name: str) -> str:
    return next((group for group, names in _GROUPS.items() if name in names), "other")


class EffectBrowser:
    """Own one live preview; recover from ordinary effect errors.

    Arrow keys choose effects/presets, / searches names/descriptions, c cycles
    categories, e edits FIELD=JSON (Tab cycles fields, Ctrl+U clears), s saves,
    and x requests export after the caller restores the terminal. q/Escape quits;
    Escape in an editor cancels editing. Edits restart the preview on update.
    Save work is queued for update, never performed by draw or input polling.
    export_request is a resolved EffectConfig; the caller owns actual encoding.
    Output files are never overwritten. Audio is opt-in; terminal is excluded.
    Ordinary startup/update/resize errors close the child and leave navigation
    available. A draw failure propagates to Player so draw remains state-pure.
    """

    def __init__(
        self,
        *,
        size: tuple[int, int] = (80, 24),
        seed: int = 42,
        include_audio: bool = False,
        theme: Theme | None = None,
        output_dir: str | Path = ".",
        export_duration: float = 5,
    ) -> None:
        _size(size)
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if type(include_audio) is not bool:
            raise TypeError("include_audio must be a bool")
        if theme is not None and not isinstance(theme, Theme):
            raise TypeError("theme must be a Theme or None")
        _seconds(export_duration, "export_duration")
        if not export_duration:
            raise ValueError("export_duration must be positive")
        self._all_names = tuple(
            name
            for name in effect_registry.names()
            if name != "terminal" and (include_audio or name != "audio")
        )
        if not self._all_names:
            raise ValueError("No previewable effects are registered")
        self.names = self._all_names
        self.categories = ("all", *sorted({_category(name) for name in self.names}))
        self.category, self.query = "all", ""
        self._index = self._preset_index = 0
        self.seed, self.theme, self._size = seed, theme or get_theme(), size
        self.output_dir, self.export_duration = Path(output_dir), export_duration
        self._child: Animation | None = None
        self._scratch = Buffer(max(1, size[1] - 5), size[0])
        self._pending = True
        self._started = self._closed = False
        self._settings: object | None = None
        self.error: str | None = None
        self.message = ""
        self._mode, self._input, self._field_index = "", "", 0
        self._actions: list[tuple[str, str]] = []
        self.export_request: EffectConfig | None = None

    @property
    def effect(self) -> str:
        if not self.names:
            raise ValueError("No matching effects; change the search or category")
        return self.names[self._index]

    @property
    def presets(self) -> tuple[str | None, ...]:
        return (None, *effect_registry.presets(self.effect)) if self.names else (None,)

    @property
    def preset(self) -> str | None:
        return self.presets[self._preset_index]

    def configuration(self) -> EffectConfig:
        """Independent resolved settings for the requested selection."""
        cls = effect_registry.get(self.effect).settings_cls
        seed = (
            self.seed
            if cls is not None and "seed" in getattr(cls, "__dataclass_fields__", {})
            else None
        )
        settings = effect_registry.resolve_settings(
            self.effect,
            preset=self.preset,
            settings=self._settings,
            seed=seed if self._settings is None else None,
        )
        if settings is None and cls is not None:
            settings = cls()
        return EffectConfig(
            self.effect,
            deepcopy(settings),
            updates_per_second=30,
            duration=self.export_duration,
            width=self._size[0],
            height=max(1, self._size[1] - 5),
        )

    def output_path(self, suffix: str) -> Path:
        """Safe basename even when applications register names with slashes."""
        stem = re.sub(
            r"[^a-zA-Z0-9_-]", "_", f"{self.effect}-{self.preset or 'custom'}"
        )
        return self.output_dir / f"preview-{stem}{suffix}"

    @property
    def command(self) -> str:
        if not self.names:
            return "# No matching effects selected."
        config = self.configuration()
        if (
            self._settings is not None
            and is_dataclass(config.settings)
            and not isinstance(config.settings, type)
        ):
            clsname = type(config.settings).__name__
            args = ", ".join(
                f"{key}={value!r}" for key, value in asdict(config.settings).items()
            )
            return (
                f"from bruhanimate import play, {clsname}\n"
                f"play({self.effect!r}, settings={clsname}({args}), fps=30, updates_per_second=30, on_resize='resize')"
            )
        options = f", preset={self.preset!r}" if self.preset else ""
        if hasattr(config.settings, "seed"):
            options += f", seed={self.seed}"
        return f"from bruhanimate import play\nplay({self.effect!r}{options}, fps=30, updates_per_second=30, on_resize='resize')"

    def _reset_selection(self) -> None:
        self._settings = None
        self._field_index = 0
        self._pending = True

    def filter(self, query: str = "", category: str = "all") -> None:
        """Stage a case-insensitive name/description filter, including no matches."""
        if category not in self.categories:
            raise ValueError(f"Unknown category: {category}")
        self.query, self.category = query, category
        self.names = tuple(
            name
            for name in self._all_names
            if (category == "all" or _category(name) == category)
            and query.casefold()
            in f"{name} {effect_registry.get(name).description}".casefold()
        )
        self._index = self._preset_index = 0
        self._reset_selection()

    def _field_text(self) -> str:
        settings = self.configuration().settings
        if settings is None or not is_dataclass(settings) or isinstance(settings, type):
            raise ValueError("This effect has no editable dataclass settings")
        names = [item.name for item in fields(settings)]
        if not names:
            raise ValueError("This effect has no editable settings")
        name = names[self._field_index % len(names)]
        return f"{name}={json.dumps(getattr(settings, name))}"

    def handle_event(self, event: int) -> bool:
        if event in (-1, 3):
            return True
        if self._mode:
            if event == 27:
                self._mode = ""
            elif event in (10, 13):
                self._actions.append((self._mode, self._input))
                self._mode = ""
            elif event == 21:
                self._input = ""
            elif event in (-300, 8, 127):
                self._input = self._input[:-1]
            elif event == 9 and self._mode == "edit":
                self._field_index += 1
                self._input = self._field_text()
            elif 32 <= event <= 126:
                self._input += chr(event)
            return False
        if event in (27, ord("q"), ord("Q")):
            return True
        if event == ord("/"):
            self._mode, self._input = "search", self.query
        elif event == ord("c"):
            self.filter(
                self.query,
                self.categories[
                    (self.categories.index(self.category) + 1) % len(self.categories)
                ],
            )
        elif self.names:
            if event in (Screen.KEY_UP, Screen.KEY_DOWN):
                self._index = (
                    self._index + (1 if event == Screen.KEY_DOWN else -1)
                ) % len(self.names)
                self._preset_index = 0
                self._reset_selection()
            elif event in (Screen.KEY_LEFT, Screen.KEY_RIGHT):
                self._preset_index = (
                    self._preset_index + (1 if event == Screen.KEY_RIGHT else -1)
                ) % len(self.presets)
                self._reset_selection()
            elif event == ord("e"):
                try:
                    self._input = self._field_text()
                    self._mode = "edit"
                except (ValueError, TypeError) as exc:
                    self.message = str(exc)
            elif event == ord("s"):
                self._actions.append(("save", ""))
            elif event == ord("x"):
                if self.effect == "audio":
                    self.message = "Live audio cannot be exported with virtual time."
                else:
                    self.export_request = self.configuration()
                    return True
        return False

    def _drop_child(self) -> None:
        child = self._child
        if child is not None:
            child.close()
            self._child = None

    def _failed(self, error: Exception) -> None:
        self.error = f"{type(error).__name__}: {error}"
        try:
            self._drop_child()
        except Exception as cleanup:
            self.error += f"; cleanup: {cleanup}"
            raise RuntimeError(self.error) from cleanup
        self._pending = False

    def _select(self) -> None:
        self.error = None
        try:
            self._drop_child()
            if not self.names:
                self.message = "No matching effects. Press / or c to change the filter."
                self._pending = False
                return
            config = self.configuration()
            child = effect_registry.create(
                self.effect,
                Buffer(self._scratch.height(), self._scratch.width()),
                " ",
                settings=config.settings,
            )
            self._child = child
            child.start()
            self.message = ""
            self._pending = False
        except Exception as exc:
            self._failed(exc)
        except BaseException:
            self.close()
            raise

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("EffectBrowser is closed")
        if not self._started:
            self._started = True
            self._select()

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started or self._closed:
            raise RuntimeError("EffectBrowser must be started before update")
        actions, self._actions = self._actions, []
        for action, text in actions:
            try:
                if action == "search":
                    self.filter(text, self.category)
                elif action == "edit":
                    self._settings = resolve_overrides(
                        effect_registry.get(self.effect),
                        None,
                        [text],
                        self.configuration().settings,
                    )
                    self._pending = True
                elif action == "save":
                    path = self.output_path(".json")
                    self.configuration().save(path)
                    self.message = f"Saved {path}"
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self.message = str(exc)
        if self._pending:
            self._select()
        if self._child is not None:
            try:
                self._child.update(dt)
            except Exception as exc:
                self._failed(exc)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self._size = size
        self._scratch = Buffer(max(1, size[1] - 5), size[0])
        if self._child is not None:
            try:
                _resize(self._child, (self._scratch.width(), self._scratch.height()))
            except Exception as exc:
                self._failed(exc)

    def draw(self, buffer: Buffer) -> None:
        buffer.clear_buffer(val=self.theme.style()._cell(" "))
        if self._child is not None:
            self._scratch.clear_buffer(val=" ")
            self._child.draw(self._scratch)
            for y, row in enumerate(self._scratch.buffer):
                if y + 2 >= buffer.height() - 3:
                    break
                for x, cell in enumerate(row):
                    if cell is not None:
                        buffer.put_char(x, y + 2, str(cell))
        title = (
            f"{self._index + 1}/{len(self.names)} {self.effect} / {self.preset or 'defaults'}"
            if self.names
            else "0 results"
        )
        lines = [
            (0, f"{title} [{self.category}]"),
            (
                1,
                effect_registry.get(self.effect).description
                if self.names
                else self.query,
            ),
            (buffer.height() - 3, "Arrows select | / search | c category | e edit"),
            (buffer.height() - 2, "s save preset | x export MP4 | q quit"),
            (
                buffer.height() - 1,
                f"{self._mode}: {self._input}_" if self._mode else self.message,
            ),
        ]
        if self.error:
            lines.append((2, self.error + " (select another effect to continue)"))
        for y, text in lines:
            style = self.theme.style(
                "error" if self.error and y == 2 else "accent" if y == 0 else "normal"
            )
            # Error/description text may contain controls: paint printable cells only.
            text = "".join(
                char if char.isascii() and char.isprintable() else "?" for char in text
            )
            for x, char in enumerate(text[: buffer.width()]):
                buffer.put_char(x, y, style._cell(char))

    def close(self) -> None:
        if not self._closed:
            self._drop_child()
            self._closed = True
