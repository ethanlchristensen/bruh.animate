"""Four bouncing windows: plasma, fire, snow, and Matrix rain.

Run ``python -m bruhanimate.demos.windows_demo``; q quits. Each window owns a
local simulation and carries its pixels, border, and title as it moves. Player
is the only playback loop. Importing or building the scene opens no resources.
"""

from bruhanimate import (
    Buffer,
    CallbackEffect,
    FireEffect,
    FireSettings,
    MatrixEffect,
    MatrixSettings,
    Panel,
    PlasmaEffect,
    PlasmaSettings,
    Scene,
    SnowEffect,
    SnowSettings,
    play,
)


def build_scene(buffer: Buffer) -> Scene:
    """Build four independently owned windows in fixed back-to-front order.

    Window sizes and bounce bounds are chosen once from the initial terminal
    dimensions. Tiny terminals clip windows safely. Motion runs at the parent's
    simulation rate; each Panel paces its effect separately. No collision
    physics, input routing, or terminal resize handling is added by this demo.
    """
    width, height = buffer.width(), buffer.height()
    window_width = min(30, max(10, (width - 8) // 2))
    window_height = min(10, max(5, (height - 6) // 2))
    bounds = (0, 1, width, max(0, height - 2))
    size = (window_width - 2, window_height - 2)
    right = max(0, width - window_width)
    bottom = max(0, bounds[3] - window_height)

    def canvas() -> Buffer:
        return Buffer(window_height - 2, window_width - 2)

    plasma = PlasmaEffect(
        canvas(), " ", PlasmaSettings(color=True, characters=False, seed=7)
    )
    fire = FireEffect(
        canvas(), " ", FireSettings(intensity=0.6, use_char_color=True, seed=11)
    )
    fire.set_fire_ascii_chars(" .:-=+*#%@")
    snow = SnowEffect(canvas(), " ", SnowSettings(intensity=0.08, seed=42))
    matrix = MatrixEffect(canvas(), " ", MatrixSettings(seed=23))
    matrix.set_gradient([232, 22, 28, 34, 40, 46, 82, 120, 157, 194])
    windows = (
        Panel(
            plasma,
            title="1 PLASMA | 30/s",
            size=size,
            bounds=bounds,
            bounce=True,
            border_background=235,
            position=(0, 1),
            velocity=(18, 3.6),
            border_color=213,
            updates_per_second=30,
        ),
        Panel(
            fire,
            title="2 FIRE | 30/s",
            size=size,
            bounds=bounds,
            bounce=True,
            border_background=235,
            position=(right, 1),
            velocity=(-15, 2.4),
            border_color=214,
            updates_per_second=30,
        ),
        Panel(
            snow,
            title="3 SNOW | 15/s",
            size=size,
            bounds=bounds,
            bounce=True,
            border_background=235,
            position=(0, bottom + 1),
            velocity=(12, -3),
            border_color=117,
            updates_per_second=15,
        ),
        Panel(
            matrix,
            title="4 MATRIX | 20/s",
            size=size,
            bounds=bounds,
            bounce=True,
            border_background=235,
            position=(right, bottom + 1),
            velocity=(-9, -1.8),
            border_color=120,
            updates_per_second=20,
        ),
    )

    def desktop(target: Buffer) -> None:
        target.clear_buffer(val="\x1b[48;5;234m \x1b[0m")

    def captions(target: Buffer) -> None:
        target.put_at(0, 0, " FOUR WINDOWS | four independent effects ".center(width))
        if height > 1:
            target.put_at(
                0,
                height - 1,
                " Bouncing windows | fixed stacking order | q quit ".center(width),
            )

    # Panel bounds protect the header/footer and contain the bouncing frames.
    return Scene(
        CallbackEffect(desktop),
        *windows,
        CallbackEffect(captions),
    )


def run(*, frames: int | None = None, fps: float = 60) -> int:
    """Play four moving effects until q or the frame limit, presenting at fps."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
    )


if __name__ == "__main__":
    run()
