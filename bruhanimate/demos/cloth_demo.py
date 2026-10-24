"""Pinned waving cloth carrying a flag, text, or custom ASCII art. Run with python -m bruhanimate.demos.cloth_demo."""

from bruhanimate import ResizePolicy, effects
from bruhanimate.effects import ClothPreset


def run(
    *,
    frames: int | None = None,
    fps: float = 30,
    preset: ClothPreset = "flag",
    on_resize: ResizePolicy = "resize",
) -> int:
    """Play a typed preset at 30 simulation updates/sec; resize retains state."""
    return effects.cloth.play(
        preset=preset,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
