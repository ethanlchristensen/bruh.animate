"""Consumer typing contracts for the additive tools."""

from threading import Event
from typing import assert_type

from bruhanimate import (
    BackgroundPlayback,
    Buffer,
    CachedAnimation,
    EffectConfig,
    HistoryPlayback,
    Label,
    Panel,
    Theme,
    Tween,
    get_theme,
)


def draw(state: int, buffer: Buffer) -> None:
    buffer.put_at(0, 0, str(state))


def producer(cancel: Event) -> list[int]:
    return [] if cancel.is_set() else [1, 2]


history = HistoryPlayback([1, 2], draw)
assert_type(history.state, int | None)
assert_type(history.bookmarks, dict[str, int])
background = BackgroundPlayback(producer, draw)
assert_type(background.state, int | None)
theme = get_theme("high_contrast")
assert_type(theme, Theme)
panel = Panel(
    Label("Ready", style=theme.style("success")), size=(20, 4), **theme.panel_options()
)
cached = CachedAnimation(panel)
tween = Tween(lambda x: panel.move_to((x, 0)), 0, 10, easing="ease_in_out")
config = EffectConfig("snow", frames=10)
assert_type(config.fps, float)
