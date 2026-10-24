"""Six resizable panels: transitions, image masks, and a public animation sequence.

Run python -m bruhanimate.demos.image_demo; q quits. An 80x40 terminal gives each
panel enough room for its small pyfiglet image. Tiny viewports clip safely.
"""

from collections.abc import Callable

from bruhanimate import (
    Animation,
    Buffer,
    Column,
    DissolveImageEffect,
    Fixed,
    FocusImageEffect,
    GlitchImageEffect,
    ImageMask,
    Label,
    Layer,
    Panel,
    PlasmaEffect,
    PlasmaSettings,
    ResizePolicy,
    Row,
    Scene,
    Slot,
    TextStyle,
    WipeImageEffect,
    play,
    text_to_image,
)

from ._image_cycle import ImageCycle


def build_scene(buffer: Buffer) -> Animation:
    """Build independently owned panels using public Layer mask/style options."""
    rows = text_to_image("bruh", font="small")

    def tile(
        name: str, make: Callable[[], Animation] | None
    ) -> Callable[[Buffer], Animation]:
        def build(local: Buffer) -> Animation:
            def content(canvas: Buffer) -> Animation:
                plasma = PlasmaEffect(
                    Buffer(canvas.height(), canvas.width()),
                    " ",
                    PlasmaSettings(color=True, characters=False, seed=7),
                )
                if make is None:
                    return Scene(
                        Layer(plasma, mask=ImageMask(rows), updates_per_second=30)
                    )
                return Scene(
                    Layer(plasma, updates_per_second=30),
                    Layer(
                        make(),
                        style=TextStyle(foreground=231, bold=True),
                        preserve_background=True,
                    ),
                )

            return Panel(
                effect_factory=content,
                size=(max(1, local.width() - 2), max(1, local.height() - 2)),
                title=name,
                fit=True,
                border_color=117,
            )

        return build

    return Column(
        Slot(
            Label("IMAGE EFFECTS | resize freely | q quit", align="center"),
            size=Fixed(1),
        ),
        Slot(
            Row(
                Slot(
                    effect_factory=tile(
                        "Glitch",
                        lambda: GlitchImageEffect(
                            rows, seed=42, repeat=True, reverse=True
                        ),
                    )
                ),
                Slot(
                    effect_factory=tile(
                        "Focus",
                        lambda: FocusImageEffect(
                            rows, seed=42, repeat=True, reverse=True
                        ),
                    )
                ),
                gap=1,
            )
        ),
        Slot(
            Row(
                Slot(
                    effect_factory=tile(
                        "Dissolve",
                        lambda: DissolveImageEffect(
                            rows, seed=42, repeat=True, reverse=True
                        ),
                    )
                ),
                Slot(effect_factory=tile("ImageMask | plasma-filled glyphs", None)),
                gap=1,
            )
        ),
        Slot(
            Row(
                Slot(
                    effect_factory=tile(
                        "Wipe right / reverse",
                        lambda: WipeImageEffect(rows, repeat=True, reverse=True),
                    )
                ),
                Slot(
                    effect_factory=tile("AnimationSequence", lambda: ImageCycle(rows))
                ),
                gap=1,
            )
        ),
        gap=1,
    ).build(buffer)


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Present at fps; transitions use simulation seconds and preserve resize state."""
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
