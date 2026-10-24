"""Five bouncing windows: plasma, fire, snow, Matrix rain, and live audio.

Run ``python -m bruhanimate.demos.windows_demo``; q quits. Each window owns a
local simulation and carries its pixels, border, and title as it moves. Player
is the only playback loop. Importing or building the scene opens no resources.
"""

from bruhanimate import (
    AudioEffect,
    AudioMode,
    AudioSettings,
    Buffer,
    CallbackEffect,
    FireEffect,
    FireSettings,
    MatrixEffect,
    MatrixSettings,
    Panel,
    PlasmaEffect,
    PlasmaSettings,
    ResizePolicy,
    Scene,
    SnowEffect,
    SnowSettings,
    play,
)


def build_scene(buffer: Buffer, *, audio_mode: AudioMode | None = "mirror") -> Scene:
    """Build five independently owned windows in fixed back-to-front order.

    audio_mode defaults to Mirror's centered bars; None omits it for
    device-free compositions/benchmarks. Audio capture starts with Scene.start
    and closes with its Panel. Missing capture dependencies are shown on screen.
    Window sizes and bounce bounds are chosen once from the initial terminal
    dimensions. Tiny terminals clip windows safely. Motion runs at the parent's
    simulation rate; each Panel paces its effect separately. No collision
    physics or input routing is added. Live resize retains window sizes and
    bounce bounds, clipping safely to the new terminal viewport.
    """
    width, height = buffer.width(), buffer.height()
    window_width = min(60, max(10, (width - 8) // 2))
    window_height = min(20, max(5, (height - 2) // 2))
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
    windows: tuple[Panel, ...] = (
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
    audio = (
        AudioEffect(
            canvas(),
            " ",
            AudioSettings(mode=audio_mode, bar_char="#", compact=True, seed=31),
        )
        if audio_mode is not None
        else None
    )
    if audio is not None:
        windows += (
            Panel(
                audio,
                title=f"5 AUDIO {audio.mode.upper()} | 30/s",
                size=size,
                bounds=bounds,
                bounce=True,
                border_background=235,
                position=(right / 2, 1 + bottom / 4),
                velocity=(21, -4.2),
                border_color=51,
                updates_per_second=30,
            ),
        )

    def desktop(target: Buffer) -> None:
        target.clear_buffer(val="\x1b[48;5;234m \x1b[0m")

    def captions(target: Buffer) -> None:
        heading = (
            " FIVE WINDOWS | five independent effects "
            if audio
            else " FOUR WINDOWS | four independent effects "
        )
        target.put_at(0, 0, heading.center(target.width()))
        if target.height() > 1:
            target.put_at(
                0,
                target.height() - 1,
                (
                    (audio._error if audio else None)
                    or " Bouncing windows | fixed stacking order | q quit "
                ).center(target.width()),
            )

    # Panel bounds protect the header/footer and contain the bouncing frames.
    return Scene(
        CallbackEffect(desktop),
        *windows,
        CallbackEffect(captions),
    )


def run(
    *,
    frames: int | None = None,
    fps: float = 60,
    on_resize: ResizePolicy = "resize",
    audio_mode: AudioMode | None = "mirror",
) -> int:
    """Play five moving effects; audio_mode=None keeps four without audio capture."""
    return play(
        effect_factory=lambda buffer: build_scene(buffer, audio_mode=audio_mode),
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
