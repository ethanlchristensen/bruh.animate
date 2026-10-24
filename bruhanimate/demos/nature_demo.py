"""Six resizable panels: water, reaction-diffusion, smoke, metaballs, cloth, terrain.

Run python -m bruhanimate.demos.nature_demo. q quits. Each panel owns a fresh
simulation; resizing reflows them without restarting or reseeding their state.
"""

from collections.abc import Callable

from bruhanimate import (
    Animation,
    Buffer,
    ClothEffect,
    ClothSettings,
    Column,
    DiffusionEffect,
    DiffusionSettings,
    Fixed,
    Label,
    MetaballsEffect,
    Panel,
    ResizableAnimation,
    ResizePolicy,
    Row,
    Slot,
    SmokeEffect,
    TerrainEffect,
    TerrainSettings,
    WaterEffect,
    WaterSettings,
    play,
)


def _slot(title: str, factory: Callable[[Buffer], Animation]) -> Slot:
    def panel(local: Buffer) -> Panel:
        border = local.width() >= 3 and local.height() >= 3
        return Panel(
            effect_factory=factory,
            size=(local.width() - 2 * border, local.height() - 2 * border),
            border=border,
            fit=True,
            title=title if border else "",
            border_color=117,
            updates_per_second=30,
        )

    return Slot(effect_factory=panel)


def build_scene(buffer: Buffer) -> ResizableAnimation:
    """Build an owned 3-by-2 gallery; hidden slots start when space becomes available."""
    layout = Column(
        Slot(Label("BRUH NATURE | resize freely | q quit"), size=Fixed(1)),
        Slot(
            Row(
                _slot(
                    "WATER",
                    lambda b: WaterEffect(
                        b, " ", WaterSettings(seed=7, drop_chance=0.12)
                    ),
                ),
                _slot(
                    "REACTION-DIFFUSION",
                    lambda b: DiffusionEffect(
                        b,
                        " ",
                        DiffusionSettings(
                            seed=7, shading=True, seed_pattern="scattered"
                        ),
                    ),
                ),
                _slot("SMOKE", lambda b: SmokeEffect(b, " ")),
            )
        ),
        Slot(
            Row(
                _slot("METABALLS", lambda b: MetaballsEffect(b, " ")),
                _slot(
                    "CLOTH",
                    lambda b: ClothEffect(b, " ", ClothSettings(pattern="text")),
                ),
                _slot(
                    "TERRAIN",
                    lambda b: TerrainEffect(
                        b, " ", TerrainSettings(seed=7, roughness=1.2)
                    ),
                ),
            )
        ),
    )
    return layout.build(buffer)


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Present at fps while each panel advances at 30 updates/sec."""
    return play(
        effect_factory=build_scene,
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
