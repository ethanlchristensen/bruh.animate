"""Configuration cycling for demos; all playback still belongs to Player."""

from collections.abc import Iterable

from bruhanimate import Animation, Buffer, ImageEffect, KeyBinding, KeyBindings, Scene
from bruhanimate.resize import _resize, _size


class Showcase:
    def __init__(
        self,
        phases: Iterable[tuple[str, Animation]],
        *,
        duration: float | None,
        title: str,
        keyboard_navigation: bool = False,
    ) -> None:
        self.phases = tuple(phases)
        if not self.phases or (duration is not None and duration <= 0):
            raise ValueError("Showcase needs phases and a positive duration or None")
        self.duration = duration
        self.title = title
        self.index = 0
        self.elapsed = 0.0
        self.scene: Scene | None = None
        navigation = (
            (
                KeyBinding("left", lambda: self._step(-1), description="previous"),
                KeyBinding("right", lambda: self._step(1), description="next"),
            )
            if keyboard_navigation
            else ()
        )
        self.bindings = KeyBindings(
            *navigation,
            KeyBinding.character("q", quit=True, description="quit"),
            KeyBinding.character("Q", quit=True),
            KeyBinding("escape", quit=True),
            KeyBinding("ctrl+c", quit=True),
        )

    def _open_phase(self) -> None:
        label, effect = self.phases[self.index]
        self.scene = Scene(
            effect,
            ImageEffect(
                f" {self.title}: {label} ({self.bindings.help_text()})", x=0, y=0
            ),
        )
        self.scene.start()

    def start(self) -> None:
        if self.scene is None:
            self._open_phase()

    def _step(self, direction: int) -> None:
        # Do not acquire resources when navigating before start or after close.
        running = self.scene is not None
        self.close()
        self.index = (self.index + direction) % len(self.phases)
        self.elapsed = 0.0
        if running:
            self._open_phase()

    def handle_event(self, event: int) -> bool:
        """Route arrows/quit; duration=None keeps selection entirely manual."""
        return self.bindings.handle_event(event)

    def update(self, dt: float) -> None:
        if self.duration is not None and self.elapsed + 1e-9 >= self.duration:
            self._step(1)
        assert self.scene is not None
        self.scene.update(dt)
        if self.duration is not None:
            self.elapsed += dt

    def draw(self, buffer: Buffer) -> None:
        if self.scene is not None:
            self.scene.draw(buffer)

    def resize(self, size: tuple[int, int]) -> None:
        """Resize every phase without restarting its simulation or phase clock."""
        _size(size)
        for _, effect in self.phases:
            _resize(effect, size)

    def close(self) -> None:
        scene, self.scene = self.scene, None
        if scene is not None:
            scene.close()
