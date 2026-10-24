"""The original v0.2 computer artwork with plasma on its screen and snow behind.

Run python -m bruhanimate.demos.tv_demo; q quits. An 80x34 terminal shows the
whole computer. Smaller viewports clip safely; resize recenters the artwork
without restarting either simulation or the two-second channel badge.
Lettering cycles through Glitch, Focus, Dissolve, and Wipe, holding for three seconds,
animating back out in reverse, and hiding for one second between entrances.
"""

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Layer,
    PlasmaEffect,
    PlasmaSettings,
    ResizePolicy,
    Scene,
    SnowEffect,
    SnowSettings,
    TextStyle,
    TimedOverlay,
    play,
    text_to_image,
)

from ._computer import (
    COMPUTER as COMPUTER,
)
from ._computer import (
    COMPUTER_WIDTH as COMPUTER_WIDTH,
)
from ._computer import (
    SCREEN_SPANS as SCREEN_SPANS,
)
from ._computer import (
    _monitor_mask,
    _origin,
    _paint,
)
from ._image_cycle import ImageCycle


class _MonitorTitle(ImageCycle):
    """Cycle entrances after the startup badge; Layer handles mask and styling."""

    def __init__(self) -> None:
        super().__init__(text_to_image("bruh", font="small"), x=8, y=3)
        self._delay = 2.0
        self._text_buffer = Buffer(len(self.rows) + 6, self.width + 16)

    def update(self, dt: float) -> None:
        waiting = min(self._delay, dt)
        self._delay -= waiting
        super().update(dt - waiting)

    def draw(self, buffer: Buffer) -> None:
        if self._delay > 0:
            return
        self._text_buffer.clear_buffer(val=None)
        super().draw(self._text_buffer)
        left, top = _origin(buffer)
        for row, cells in enumerate(self._text_buffer.buffer):
            for column, glyph in enumerate(cells):
                if glyph is not None:
                    buffer.put_char(left + 23 - 8 + column, top + 6 - 3 + row, glyph)


def build_scene(buffer: Buffer) -> Scene:
    """Compose snow, computer art, plasma, a revealing title, badge, and captions.

    Rows between each silhouette's first/last glyph paint opaque spaces, hiding
    background snow inside the body. Plasma replaces only the monitor opening.
    Artwork is kept at its original size and recentered from the draw viewport.
    Simulations retain independent full-viewport rasters and resize adapters.
    Use on_complete="hold" to continue after the finite badge expires.
    """

    def computer(target: Buffer) -> None:
        left, top = _origin(target)
        for row, text in enumerate(COMPUTER):
            start = len(text) - len(text.lstrip())
            _paint(target, left + start, top + row, text[start:], "38;5;250;49")

    def badge(target: Buffer) -> None:
        left, top = _origin(target)
        _paint(target, left + 24, top + 7, " CH 01 / PLASMA ", "38;5;231;48;5;24")

    title = _MonitorTitle()

    def captions(target: Buffer) -> None:
        target.put_at(0, 0, " BRUH COMPUTER | Plasma on air ".center(target.width()))
        if target.height() > 1:
            target.put_at(
                0,
                target.height() - 1,
                f" Snow 15/s | Plasma 30/s | {title.phase_name} | q quit ".center(
                    target.width()
                ),
            )

    width, height = buffer.width(), buffer.height()
    snow = SnowEffect(Buffer(height, width), " ", SnowSettings(intensity=0.04, seed=42))
    plasma = PlasmaEffect(
        Buffer(height, width), " ", PlasmaSettings(color=True, characters=False, seed=7)
    )
    return Scene(
        Layer(snow, updates_per_second=15),
        CallbackEffect(computer),
        Layer(plasma, updates_per_second=30, mask=_monitor_mask),
        Layer(
            title,
            mask=_monitor_mask,
            style=TextStyle(foreground=231, bold=True),
            preserve_background=True,
        ),
        TimedOverlay(CallbackEffect(badge), duration=2),
        CallbackEffect(captions),
    )


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Play until q or the frame limit; the badge does not stop the animation."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_complete="hold",
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
