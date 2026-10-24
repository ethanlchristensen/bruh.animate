"""Damped water ripples with reflecting edges and interacting impulses. Run with python -m bruhanimate.demos.water_demo."""

from bruhanimate import ResizePolicy, effects
from bruhanimate.effects import WaterPreset


def run(
    *,
    frames: int | None = None,
    fps: float = 30,
    preset: WaterPreset = "pond",
    on_resize: ResizePolicy = "resize",
) -> int:
    """Play a typed preset at 30 simulation updates/sec; resize retains state."""
    return effects.water.play(
        preset=preset,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
