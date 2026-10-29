"""An original spaceship flying through the warp starfield.

Run ``python -m bruhanimate.demos.warp_demo``. q, Escape or Ctrl+C quits.
Player owns the loop; Scene owns the starfield and animated ship. Resize keeps
flight and engine phase, choosing compact art when the full ship cannot fit.
"""

import math

from bruhanimate import (
    Buffer,
    Layer,
    ResizePolicy,
    Scene,
    Sprite,
    SpriteAsset,
    SpriteClip,
    StarfieldEffect,
    effects,
    play,
)


def _asset(rows: tuple[str, ...]) -> SpriteAsset:
    """Use the terminal background; dots are transparent, hull spaces opaque."""
    plain = SpriteAsset.from_text("\n".join(rows), transparent=".")

    def style(cell: str | None) -> str | None:
        if cell is None:
            return None
        color = 159 if cell in "AoO" else 51 if cell in "vV~" else 250
        return f"\x1b[38;5;{color};49m{cell}\x1b[0m"

    return SpriteAsset([[style(cell) for cell in row] for row in plain.cells])


def _clips() -> tuple[SpriteClip, ...]:
    hull = (
        "............^............",
        ".........../A\\...........",
        "........../   \\..........",
        "........./ [o] \\.........",
        "....____/|     |\\____....",
        ".../_____|  O  |_____\\...",
        ".........|_____|.........",
        ".........[V] [V].........",
    )
    exhaust = (
        (
            "..........v...v..........",
            "..........~...~..........",
            ".........................",
        ),
        (
            "..........V...V..........",
            "..........v...v..........",
            "..........~...~..........",
        ),
        (
            "..........v...V..........",
            "..............v..........",
            "..............~..........",
        ),
    )
    return (
        SpriteClip([_asset(hull + tail) for tail in exhaust], frame_duration=0.1),
        SpriteClip(
            [_asset(("..^..", "/[o]\\", tail)) for tail in (".v.v.", ".V.V.", ".~.~.")],
            frame_duration=0.1,
        ),
        SpriteClip([_asset(("^",))]),
    )


class _Spaceship:
    def __init__(self, size: tuple[int, int]):
        self.clips = _clips()
        self.ships = tuple(Sprite(clip) for clip in self.clips)
        self.scene = Scene(*self.ships)
        self.phase = 0.0
        self.size = size
        self.active = 0
        self.resize(size)

    def _place(self) -> None:
        width, height = self.size
        margin = 1 if height >= 7 and width >= 32 else 0
        available = height - 2 * margin
        self.active = next(
            i
            for i, clip in enumerate(self.clips)
            if clip.frames[0].width <= width and clip.frames[0].height <= available
        )
        for i, ship in enumerate(self.ships):
            ship.set_visible(i == self.active)
        frame = self.clips[self.active].frames[0]
        slack_x, slack_y = width - frame.width, available - frame.height
        x = slack_x / 2 + math.sin(self.phase) * min(5, slack_x / 2)
        y = margin + slack_y * 0.6 + math.sin(self.phase * 2) * min(1, slack_y * 0.4)
        self.ships[self.active].position = (round(x), round(y))

    def start(self) -> None:
        self.scene.start()

    def update(self, dt: float) -> None:
        self.scene.update(dt)
        self.phase = (self.phase + dt * 0.7) % math.tau
        self._place()

    def resize(self, size: tuple[int, int]) -> None:
        self.scene.resize(size)
        self.size = size
        self._place()

    def draw(self, buffer: Buffer) -> None:
        self.scene.draw(buffer)
        if buffer.height() >= 7 and buffer.width() >= 32:
            buffer.put_at(0, 0, " WARP DRIVE // ENGAGED ")
            buffer.put_at(0, buffer.height() - 1, " q / Esc quit | resize freely ")

    def close(self) -> None:
        self.scene.close()


def build_scene(buffer: Buffer) -> Scene:
    """Build an inert, seeded, endless scene suitable for playback or capture.

    Starfield advances at 30 ticks/sec. Ship drift and engine clips use seconds.
    Scene owns both layers; draws are pure and blank hull cells occlude stars.
    """
    settings = effects.starfield.preset("warp")
    settings.seed = 42
    return Scene(
        Layer(StarfieldEffect(buffer, " ", settings), updates_per_second=30),
        _Spaceship((buffer.width(), buffer.height())),
    )


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Fly until quit or the frame limit, preserving state across live resize."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
