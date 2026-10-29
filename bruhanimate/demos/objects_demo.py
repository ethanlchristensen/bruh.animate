"""Shared sprite art, clipped scenery and dynamically owned sparks.

Run ``python -m bruhanimate.demos.objects_demo``. Player owns the only loop;
the demo keeps its movement and spawning rules in application code.
"""

from bruhanimate import (
    Buffer,
    CallbackEffect,
    ObjectGroup,
    ResizePolicy,
    Sprite,
    SpriteAsset,
    SpriteClip,
    draw_ellipse,
    draw_line,
    draw_rect,
    play,
)


class _ObjectsDemo:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        wings = SpriteClip(
            [
                SpriteAsset.from_text(text, transparent=" ")
                for text in ("\\o/", "-o-", "/o\\")
            ],
            frame_duration=0.15,
        )
        self.flyers = [
            Sprite(
                wings,
                position=(3 + index * 9, 3 + index * 3),
                velocity=(4 + index * 2, 0),
            )
            for index in range(3)
        ]
        self.group = ObjectGroup({"scenery": CallbackEffect(self._scenery)})
        for index, flyer in enumerate(self.flyers):
            self.group.add(f"flyer-{index}", flyer)
        self.spark_clip = SpriteClip(
            [SpriteAsset.from_text(char) for char in ("+", "*", ".")],
            frame_duration=0.2,
            repeat=False,
        )
        self.spark: Sprite | None = None
        self.time = 0.0

    def _scenery(self, buffer: Buffer) -> None:
        width, height = buffer.width(), buffer.height()
        draw_rect(buffer, (0, 0, width, height), "\x1b[36m.\x1b[0m")
        draw_ellipse(
            buffer,
            (width // 3, height // 3, max(1, width // 3), max(1, height // 2)),
            "\x1b[34m~\x1b[0m",
            filled=True,
        )
        draw_line(buffer, (0, height - 2), (width - 1, height - 2), "\x1b[32m_\x1b[0m")
        buffer.put_at(2, 0, " Shared sprites / live objects ")

    def start(self) -> None:
        self.group.resize(self.size)
        self.group.start()

    def resize(self, size: tuple[int, int]) -> None:
        self.group.resize(size)
        self.size = size

    def update(self, dt: float) -> None:
        if self.spark is not None and self.spark.finished:
            self.group.remove("spark")
            self.spark = None
        self.time += dt
        if self.time >= 1:
            self.time %= 1
            if self.spark is None:
                self.spark = Sprite(self.spark_clip, position=self.flyers[0].position)
                self.group.add("spark", self.spark)
        self.group.update(dt)
        width, height = self.size
        for flyer in self.flyers:
            x, y = flyer.position
            flyer.position = (x % width, y % height)

    def draw(self, buffer: Buffer) -> None:
        self.group.draw(buffer)

    def close(self) -> None:
        self.group.close()


def build(buffer: Buffer) -> _ObjectsDemo:
    """Build an inert demo for play/capture; the caller owns its lifecycle."""
    return _ObjectsDemo((buffer.width(), buffer.height()))


def run(
    *, frames: int | None = None, fps: float = 30, on_resize: ResizePolicy = "resize"
) -> int:
    return play(effect_factory=build, frames=frames, fps=fps, on_resize=on_resize)


if __name__ == "__main__":
    run()
