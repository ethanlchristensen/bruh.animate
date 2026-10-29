"""Consumer typing contracts for the additive tools."""

from threading import Event
from typing import assert_type

from bruhanimate import (
    ActionQueue,
    AnimationControl,
    BackgroundPlayback,
    Buffer,
    Button,
    CachedAnimation,
    Camera2D,
    Checkbox,
    EffectConfig,
    FocusGroup,
    FocusStack,
    FocusTarget,
    HistoryPlayback,
    Label,
    ObjectGroup,
    Panel,
    Sprite,
    SpriteAsset,
    SpriteClip,
    TextInput,
    Theme,
    Tile,
    TileMap,
    Tween,
    draw_ellipse,
    draw_line,
    draw_rect,
    get_theme,
)

field = TextInput("name", "Player", on_change=lambda value: None)
checkbox = Checkbox("effects", "Effects", checked=True)
button = Button("apply", "Apply", lambda: None)
form = FocusGroup(field.focus, checkbox.focus, button.focus)
router = FocusStack(form)
assert_type(field.value, str)
assert_type(field.cursor, int)
assert_type(checkbox.checked, bool)
assert_type(field.focus, FocusTarget)
assert_type(router.active, FocusGroup | None)

actions = ActionQueue[str](capacity=8)
assert_type(actions.drain(), tuple[str, ...])
assert_type(actions.push("move"), bool)
controlled = AnimationControl(Sprite(SpriteAsset.from_text("X")), mode="fixed")
assert_type(controlled.time_scale, float)
assert_type(controlled.finished, bool | None)

world = TileMap([".#"], {".": Tile("."), "#": Tile("#", solid=True)})
camera = Camera2D((2, 1), world_size=(world.width, world.height))
assert_type(camera.position, tuple[int, int])
assert_type(camera.visible_bounds, tuple[int, int, int, int])
assert_type(world.move((0, 0, 1, 1), (1, 0)), tuple[int, int])
assert_type(world.tile_at((0, 0)), Tile)

asset = SpriteAsset.from_text("X")
clip = SpriteClip([asset])
sprite = Sprite(clip, position=(1, 2), velocity=(3, 0))
group = ObjectGroup({"sprite": sprite})
assert_type(sprite.position, tuple[float, float])
assert_type(sprite.finished, bool | None)
assert_type(group.names, tuple[str, ...])
assert_type(asset.cells, tuple[tuple[str | None, ...], ...])
target = Buffer(3, 5)
draw_line(target, (0, 0), (4, 2))
draw_rect(target, (0, 0, 5, 3))
draw_ellipse(target, (0, 0, 5, 3), filled=True)


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
