"""Configuration cycling for demos; all playback still belongs to Player."""

from bruhanimate import ImageEffect, Scene


class Showcase:
    def __init__(self, phases, *, duration, title):
        self.phases = tuple(phases)
        if not self.phases or duration <= 0:
            raise ValueError("Showcase needs phases and a positive duration")
        self.duration = duration
        self.title = title
        self.index = 0
        self.elapsed = 0.0
        self.scene = None

    def _open_phase(self):
        label, effect = self.phases[self.index]
        self.scene = Scene(
            effect, ImageEffect(f" {self.title}: {label} (q quits)", x=0, y=0)
        )
        self.scene.start()

    def start(self):
        if self.scene is None:
            self._open_phase()

    def update(self, dt):
        if self.elapsed + 1e-9 >= self.duration:
            self.close()
            self.index = (self.index + 1) % len(self.phases)
            self.elapsed = 0.0
            self._open_phase()
        self.scene.update(dt)
        self.elapsed += dt

    def draw(self, buffer):
        self.scene.draw(buffer)

    def close(self):
        scene, self.scene = self.scene, None
        if scene is not None:
            scene.close()
