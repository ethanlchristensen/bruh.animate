"""A native effect with ten simulation ticks and sixty presentations per second."""

from bruhanimate import BaseEffect, ImageEffect, Scene, play


class StepEffect(BaseEffect):
    def __init__(self, buffer):
        super().__init__(buffer, " ")
        self.step = 0

    def update(self, dt):
        self.buffer.clear_buffer()
        self.buffer.put_at_center(self.buffer.height() // 2, f"Step {self.step}")
        self.buffer.put_char(self.step % self.buffer.width(), 0, "*")
        self.step += 1


def build(buffer):
    return Scene(StepEffect(buffer), ImageEffect("10 updates / 60 draws", x=0, y=1))


def run(*, frames=None, fps=60):
    return play(effect_factory=build, fps=fps, updates_per_second=10, frames=frames)


if __name__ == "__main__":
    run()
