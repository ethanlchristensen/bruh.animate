"""Explore an original tile world with arrows/WASD; collect all five stars.

P pauses, R resets, Q/Escape quits. Input queues at most 16 commands, drops new
commands when full, and consumes one per simulation update. Movement is one grid
cell per command, including terminal key-repeat events, not held-key detection.
Player remains the only loop/poller. Game rules live here, outside the library.
"""

from functools import partial

from bruhanimate import (
    ActionQueue,
    Buffer,
    Camera2D,
    KeyBinding,
    KeyBindings,
    ResizePolicy,
    Sprite,
    SpriteAsset,
    SpriteClip,
    Tile,
    TileMap,
    play,
)
from bruhanimate._validation import _seconds
from bruhanimate.geometry import Point
from bruhanimate.resize import _size

STARS = frozenset({(5, 3), (19, 7), (33, 12), (47, 20), (63, 4)})


def make_world() -> TileMap:
    """Construct a deterministic public fixture with gates through each wall."""
    rows = [["."] * 70 for _ in range(25)]
    for y in range(25):
        for x in range(70):
            if (
                x in (0, 69)
                or y in (0, 24)
                or (x in (12, 26, 40, 54) and y not in (5, 17))
            ):
                rows[y][x] = "#"
    return TileMap(
        rows,
        {
            ".": Tile("\x1b[38;5;238m.\x1b[0m"),
            "#": Tile("\x1b[38;5;66m#\x1b[0m", solid=True),
        },
    )


class TopDownGame:
    """Own a player sprite; borrow immutable map data and own camera/game state.

    Queue events through handle_event and advance through update(dt). Pause
    suppresses sprite updates and movement; resize retains world/game state.
    Completion is displayed in the HUD; the animation stays endless until quit.
    """

    def __init__(self, size: Point = (40, 14)) -> None:
        self.world = make_world()
        self.camera = Camera2D((1, 1), world_size=(self.world.width, self.world.height))
        self.hero = Sprite(
            SpriteClip(
                [
                    SpriteAsset([["\x1b[93m@\x1b[0m"]]),
                    SpriteAsset([["\x1b[97m@\x1b[0m"]]),
                ],
                frame_duration=0.3,
            )
        )
        self.position = (2, 2)
        self.remaining = set(STARS)
        self.paused = False
        self._commands: ActionQueue[Point | str] = ActionQueue(capacity=16)
        self._started = self._closed = False
        self.bindings = KeyBindings(
            KeyBinding("up", partial(self.enqueue, (0, -1))),
            KeyBinding("down", partial(self.enqueue, (0, 1))),
            KeyBinding("left", partial(self.enqueue, (-1, 0))),
            KeyBinding("right", partial(self.enqueue, (1, 0))),
            *(
                KeyBinding.character(key, partial(self.enqueue, delta))
                for key, delta in (
                    ("w", (0, -1)),
                    ("s", (0, 1)),
                    ("a", (-1, 0)),
                    ("d", (1, 0)),
                )
            ),
            KeyBinding.character("p", partial(self.enqueue, "pause")),
            KeyBinding.character("r", partial(self.enqueue, "reset")),
            KeyBinding.character("q", quit=True),
            KeyBinding.character("Q", quit=True),
            KeyBinding("escape", quit=True),
            KeyBinding("ctrl+c", quit=True),
        )
        self.resize(size)

    def enqueue(self, command: Point | str) -> None:
        if not self._closed:
            self._commands.push(command)

    def handle_event(self, event: int) -> bool:
        return self.bindings.handle_event(event)

    def _sync_view(self) -> None:
        self.camera.follow(self.position)
        self.hero.position = self.camera.world_to_screen(
            self.position, origin=self.origin
        )

    def resize(self, size: Point) -> None:
        _size(size)
        self.size = size
        self.origin = (0, 1) if size[1] >= 3 else (0, 0)
        self.camera.resize((size[0], size[1] - 2 if size[1] >= 3 else size[1]))
        self._sync_view()

    def start(self) -> None:
        self.hero.start()
        self._started = True

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError("game must be started and not closed before update")
        _seconds(dt, "dt")
        commands = self._commands.drain()
        command = commands[0] if commands else None
        if command == "pause":
            self.paused = not self.paused
        elif command == "reset":
            self.position = (2, 2)
            self.remaining = set(STARS)
            self.paused = False
            self._commands.clear()
        elif isinstance(command, tuple) and not self.paused:
            self.position = self.world.move((*self.position, 1, 1), command)
            self.remaining.discard(self.position)
        if not self.paused:
            self.hero.update(dt)
        self._sync_view()

    def draw(self, buffer: Buffer) -> None:
        if self._closed:
            return
        self.world.draw(buffer, camera=self.camera, origin=self.origin)
        for point in self.remaining:
            x, y = self.camera.world_to_screen(point, origin=self.origin)
            if (
                self.origin[0] <= x < self.origin[0] + self.camera.viewport[0]
                and self.origin[1] <= y < self.origin[1] + self.camera.viewport[1]
            ):
                buffer.put_char(x, y, "\x1b[93m*\x1b[0m")
        self.hero.draw(buffer)
        if self.size[1] >= 3:
            status = (
                "PAUSED"
                if self.paused
                else "ALL STARS FOUND"
                if not self.remaining
                else "EXPLORE"
            )
            buffer.put_at(
                0,
                0,
                f"{status} | stars {5 - len(self.remaining)}/5 | {self.position}".ljust(
                    buffer.width()
                ),
            )
            help_text = "Arrows/WASD | p pause | r reset | q quit"
            if buffer.width() < len(help_text):
                help_text = "WASD p:pause r:reset q:quit"
            if buffer.width() < len(help_text):
                help_text = "WASD | q quit"
            if buffer.width() < len(help_text):
                help_text = "q quit"
            buffer.put_at(0, self.size[1] - 1, help_text.ljust(buffer.width()))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._commands.clear()
        self.hero.close()


def build(buffer: Buffer) -> TopDownGame:
    return TopDownGame((buffer.width(), buffer.height()))


def run(
    *, frames: int | None = None, fps: float = 30, on_resize: ResizePolicy = "resize"
) -> int:
    game: TopDownGame | None = None

    def factory(buffer: Buffer) -> TopDownGame:
        nonlocal game
        game = build(buffer)
        return game

    def event(code: int) -> bool:
        return game.handle_event(code) if game is not None else False

    return play(
        effect_factory=factory,
        event_handler=event,
        frames=frames,
        fps=fps,
        updates_per_second=12,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
