"""Flow procedural animation. Run with python -m bruhanimate.demos.flow_demo."""

from bruhanimate import ResizePolicy, effects
from bruhanimate.effects import FlowPreset


def run(
    *,
    frames: int | None = None,
    fps: float = 30,
    preset: FlowPreset = "neon",
    on_resize: ResizePolicy = "resize",
) -> int:
    """Play a typed preset at 30 simulation updates/sec; resize retains state."""
    return effects.flow.play(
        preset=preset,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
