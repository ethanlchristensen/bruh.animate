"""Interactive registry browser using the same Player as every other animation."""

from ._validation import _seconds
from .bruheffect.registry import effect_registry
from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen
from .player import Animation
from .resize import _resize, _size
from .themes import Theme, get_theme


class EffectBrowser:
    """Own one live registry preview with keyboard selection and copyable code.

    Up/down selects effects; left/right selects presets (including defaults).
    q/Escape/Ctrl+C exits. Selection requests are applied in update; draw only
    reads state. Old previews close before replacements start; resizing preserves
    the selected effect's state. Audio is excluded unless include_audio=True;
    terminal subprocess effects are always excluded. command returns Python for
    the currently requested selection. Construction starts no preview/resources.
    """

    def __init__(
        self,
        *,
        size: tuple[int, int] = (80, 24),
        seed: int = 42,
        include_audio: bool = False,
        theme: Theme | None = None,
    ) -> None:
        _size(size)
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if type(include_audio) is not bool:
            raise TypeError("include_audio must be a bool")
        if theme is not None and not isinstance(theme, Theme):
            raise TypeError("theme must be a Theme or None")
        self.names = tuple(
            name
            for name in effect_registry.names()
            if name != "terminal" and (include_audio or name != "audio")
        )
        if not self.names:
            raise ValueError("No previewable effects are registered")
        self._index = self._preset_index = 0
        self.seed = seed
        self.theme = theme or get_theme()
        self._size = size
        self._child: Animation | None = None
        self._scratch = Buffer(max(1, size[1] - 4), size[0])
        self._pending = True
        self._started = self._closed = False

    @property
    def effect(self) -> str:
        return self.names[self._index]

    @property
    def presets(self) -> tuple[str | None, ...]:
        return (None, *effect_registry.presets(self.effect))

    @property
    def preset(self) -> str | None:
        return self.presets[self._preset_index]

    @property
    def command(self) -> str:
        options = f", preset={self.preset!r}" if self.preset else ""
        cls = effect_registry.get(self.effect).settings_cls
        if cls is not None and "seed" in getattr(cls, "__dataclass_fields__", {}):
            options += f", seed={self.seed}"
        return f"from bruhanimate import play\nplay({self.effect!r}{options}, fps=30, updates_per_second=30, on_resize='resize')"

    def handle_event(self, event: int) -> bool:
        if event in (-1, 3, 27, ord("q"), ord("Q")):
            return True
        if event in (Screen.KEY_UP, Screen.KEY_DOWN):
            self._index = (self._index + (1 if event == Screen.KEY_DOWN else -1)) % len(
                self.names
            )
            self._preset_index = 0
            self._pending = True
        elif event in (Screen.KEY_LEFT, Screen.KEY_RIGHT):
            self._preset_index = (
                self._preset_index + (1 if event == Screen.KEY_RIGHT else -1)
            ) % len(self.presets)
            self._pending = True
        return False

    def _select(self) -> None:
        previous, self._child = self._child, None
        if previous is not None:
            previous.close()
        cls = effect_registry.get(self.effect).settings_cls
        seed = (
            self.seed
            if cls is not None and "seed" in getattr(cls, "__dataclass_fields__", {})
            else None
        )
        child = effect_registry.create(
            self.effect,
            Buffer(self._scratch.height(), self._scratch.width()),
            " ",
            preset=self.preset,
            seed=seed,
        )
        self._child = child
        try:
            child.start()
        except BaseException:
            self.close()
            raise
        self._pending = False

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
        if self._pending:
            self._select()
        assert self._child is not None
        self._child.update(dt)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self._size = size
        self._scratch = Buffer(max(1, size[1] - 4), size[0])
        if self._child is not None:
            _resize(self._child, (self._scratch.width(), self._scratch.height()))

    def draw(self, buffer: Buffer) -> None:
        buffer.clear_buffer(val=self.theme.style()._cell(" "))
        if self._child is not None:
            self._scratch.clear_buffer(val=" ")
            self._child.draw(self._scratch)
            for y, row in enumerate(self._scratch.buffer):
                if y + 2 >= buffer.height() - 2:
                    break
                for x, cell in enumerate(row):
                    if cell is not None:
                        buffer.put_char(x, y + 2, str(cell))
        lines = (
            (
                0,
                f"{self._index + 1}/{len(self.names)}  {self.effect} / {self.preset or 'defaults'}",
            ),
            (1, effect_registry.get(self.effect).description),
            (buffer.height() - 2, "Up/Down effects | Left/Right presets | q quit"),
            (buffer.height() - 1, "Selected Python command prints after quitting."),
        )
        for y, text in lines:
            style = self.theme.style("accent" if y == 0 else "normal")
            for x, char in enumerate(text[: buffer.width()]):
                buffer.put_char(x, y, style._cell(char))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            child, self._child = self._child, None
            if child is not None:
                child.close()
