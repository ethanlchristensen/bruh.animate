"""A retro TV showing plasma while snow falls behind its opaque cabinet.

Run ``python -m bruhanimate.demos.tv_demo``; q quits. Snow updates at 15/s,
plasma at 30/s, and Player presents at 60 FPS. A channel badge lasts two seconds.
No terminal or other resources are opened until run() is called.
"""

from bruhanimate import (
    Buffer,
    CallbackEffect,
    ImageEffect,
    Layer,
    PlasmaEffect,
    PlasmaSettings,
    Scene,
    SnowEffect,
    SnowSettings,
    TimedOverlay,
    play,
)


def _paint(buffer: Buffer, x: int, y: int, text: str, style: str) -> None:
    """Style each cell separately so clipping cannot cut an ANSI sequence."""
    for offset, char in enumerate(text):
        buffer.put_char(x + offset, y, f"\x1b[{style}m{char}\x1b[0m")


def build_scene(buffer: Buffer) -> Scene:
    """Build an owned scene using separate full-size effect buffers.

    The screen region clips destination cells; it does not resize the plasma
    simulation. Layout is computed once, with smaller terminals clipping the TV.
    The badge is a finite child: use on_complete="hold" to keep playing after it
    expires, including when capturing this scene with virtual time.
    """
    width, height = buffer.width(), buffer.height()
    cabinet_width = min(64, max(24, width - 12))
    cabinet_height = min(20, max(10, height - 8))
    left = (width - cabinet_width) // 2
    top = (height - cabinet_height) // 2
    screen = (left + 3, top + 2, cabinet_width - 13, cabinet_height - 4)
    sx, sy, sw, sh = screen
    wood = "38;5;223;48;5;94"
    bezel = "38;5;250;48;5;235"

    def cabinet(target: Buffer) -> None:
        # Plain/colored spaces paint: snow must not show through the cabinet.
        for row in range(cabinet_height):
            _paint(target, left, top + row, " " * cabinet_width, wood)
        _paint(target, left, top, "+" + "-" * (cabinet_width - 2) + "+", wood)
        _paint(
            target,
            left,
            top + cabinet_height - 1,
            "+" + "-" * (cabinet_width - 2) + "+",
            wood,
        )
        for row in range(1, cabinet_height - 1):
            _paint(target, left, top + row, "|", wood)
            _paint(target, left + cabinet_width - 1, top + row, "|", wood)
        _paint(target, sx - 1, sy - 1, "+" + "-" * sw + "+", bezel)
        _paint(target, sx - 1, sy + sh, "+" + "-" * sw + "+", bezel)
        for row in range(sh):
            _paint(target, sx - 1, sy + row, "|" + " " * sw + "|", bezel)
        controls = sx + sw + 3
        _paint(target, controls, top + 2, "( O )", wood)
        _paint(target, controls, top + 4, "( o )", wood)
        for row in range(top + 6, top + cabinet_height - 2):
            _paint(target, controls, row, "=====", wood)
        _paint(target, controls, top + cabinet_height - 2, "* ON", wood)
        center = left + cabinet_width // 2
        _paint(target, center - 3, top - 2, "\\   /", "37")
        _paint(target, center - 2, top - 1, "\\_/", "37")
        _paint(target, left + 4, top + cabinet_height, "//", "38;5;180")
        _paint(
            target,
            left + cabinet_width - 6,
            top + cabinet_height,
            "\\\\",
            "38;5;180",
        )

    def captions(target: Buffer) -> None:
        target.put_at(0, 0, " BRUH TV | Plasma on air ".center(width))
        if height > 1:
            target.put_at(
                0, height - 1, " Snow 15/s | Plasma 30/s | q quit ".center(width)
            )

    # Separate instances own separate rasters; no mutable buffer is shared.
    snow = SnowEffect(Buffer(height, width), " ", SnowSettings(intensity=0.04, seed=42))
    plasma = PlasmaEffect(
        Buffer(height, width),
        " ",
        PlasmaSettings(color=True, characters=False, seed=7),
    )
    return Scene(
        Layer(snow, updates_per_second=15),
        CallbackEffect(cabinet),
        Layer(plasma, region=screen, updates_per_second=30),
        Layer(
            TimedOverlay(
                ImageEffect(" CH 01 / PLASMA ", x=sx + 1, y=sy + 1), duration=2
            ),
            region=screen,
        ),
        CallbackEffect(captions),
    )


def run(*, frames: int | None = None, fps: float = 60) -> int:
    """Play until q or the frame limit; the channel badge does not stop the TV."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_complete="hold",
    )


if __name__ == "__main__":
    run()
