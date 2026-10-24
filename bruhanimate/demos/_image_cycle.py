"""Demo configuration built entirely on the public sequencing API."""

from collections.abc import Sequence

from bruhanimate import (
    AnimationSequence,
    DissolveImageEffect,
    FocusImageEffect,
    GlitchImageEffect,
    SequenceStep,
    WipeImageEffect,
)


class ImageCycle(AnimationSequence):
    """Glitch, Focus, Dissolve and Wipe, each entering, holding, and reversing."""

    names = ("Glitch", "Focus", "Dissolve", "Wipe")

    def __init__(
        self, rows: Sequence[str], *, x: float | None = None, y: float | None = None
    ) -> None:
        self.rows = tuple(rows)
        self.width = max(map(len, self.rows), default=0)
        # Glitch duration: launch each glyph, then let the final one arrive.
        glitch_duration = (
            sum(char != " " for row in self.rows for char in row) / 18 + 0.65
        )
        super().__init__(
            SequenceStep(
                lambda: GlitchImageEffect(self.rows, x=x, y=y, seed=42, reverse=True),
                duration=2 * glitch_duration + 3,
                gap=1,
                name="Glitch",
            ),
            SequenceStep(
                lambda: FocusImageEffect(
                    self.rows,
                    x=x,
                    y=y,
                    duration=2.5,
                    scatter=(8, 3),
                    seed=42,
                    reverse=True,
                ),
                duration=8,
                gap=1,
                name="Focus",
            ),
            SequenceStep(
                lambda: DissolveImageEffect(
                    self.rows, x=x, y=y, duration=2.5, seed=42, reverse=True
                ),
                duration=8,
                gap=1,
                name="Dissolve",
            ),
            SequenceStep(
                lambda: WipeImageEffect(
                    self.rows, x=x, y=y, duration=2.5, direction="right", reverse=True
                ),
                duration=8,
                gap=1,
                name="Wipe",
            ),
            repeat=True,
        )
