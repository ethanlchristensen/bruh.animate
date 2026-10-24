"""
Copyright 2023 Ethan Christensen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""Select audio modes with left/right arrows; no automatic cycling. q quits."""

from collections.abc import Iterable
from typing import get_args

from bruhanimate import (
    Animation,
    Buffer,
    KeyBinding,
    KeyBindings,
    Layer,
    ResizePolicy,
    Scene,
    SnowEffect,
    SnowSettings,
    effect_registry,
    play,
)
from bruhanimate.bruheffect import AudioSettings
from bruhanimate.resize import _resize

from ._computer import ComputerFrame, ComputerStyle
from ._showcase import Showcase

TARGET_FPS = 30


MODE_HELP = {
    "Tiles": "Frequency blocks | bass on the left, treble on the right",
    "Glow": "Bass: amber pools | mids: violet | treble: cyan highlights",
    "Objects": "Bass grows blocks 3x3 to touching | mids move | treble sparkles",
    "Bars": "Low frequencies on the left; high on the right | caps show peaks",
    "Mirror": "Low to high frequencies | louder bands grow from the center",
    "Waveform": "Volume history | newest sound on the right",
    "Spectrum": "Low pitch at bottom; high at top | newest sound on the right",
}


class AudioShowcase(Showcase):
    """Own selected audio locally; C changes the computer without restarting capture."""

    def __init__(
        self,
        phases: Iterable[tuple[str, Animation]],
        *,
        size: tuple[int, int],
        computer: ComputerStyle = "classic",
    ) -> None:
        super().__init__(phases, duration=None, title="Audio", keyboard_navigation=True)
        self.computer = computer
        self.frame = ComputerFrame(size, computer)
        self._screen = Buffer(self.frame.screen_size[1], self.frame.screen_size[0])
        self._background = Scene(
            Layer(
                SnowEffect(
                    Buffer(size[1], size[0]), " ", SnowSettings(intensity=0.04, seed=42)
                ),
                updates_per_second=15,
            )
        )
        self.bindings = KeyBindings(
            *self.bindings.bindings,
            KeyBinding.character("c", self._switch_computer, description="computer"),
            KeyBinding.character("C", self._switch_computer),
        )

    def _open_phase(self) -> None:
        _, effect = self.phases[self.index]
        self.scene = Scene(effect)
        self.scene.start()

    def _switch_computer(self) -> None:
        styles = get_args(ComputerStyle)
        self.computer = styles[(styles.index(self.computer) + 1) % len(styles)]
        self.resize(self.frame.size)

    def start(self) -> None:
        try:
            self._background.start()
            super().start()
        except BaseException:
            self.close()
            raise

    def _step(self, direction: int) -> None:
        # Mode changes close only audio; snow keeps its particles and clock.
        running = self.scene is not None
        super().close()
        self.index = (self.index + direction) % len(self.phases)
        self.elapsed = 0.0
        if running:
            self._open_phase()

    def update(self, dt: float) -> None:
        super().update(dt)
        self._background.update(dt)

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._background.close()

    def resize(self, size: tuple[int, int]) -> None:
        """Refit all modes to the local monitor, preserving capture and selection."""
        frame = ComputerFrame(size, self.computer)
        for _, effect in self.phases:
            _resize(effect, frame.screen_size)
        self._background.resize(size)
        self.frame = frame
        self._screen = Buffer(frame.screen_size[1], frame.screen_size[0])

    def draw(self, buffer: Buffer) -> None:
        if self.scene is not None:
            buffer.clear_buffer(val=" ")
            self._background.draw(buffer)
            self._screen.clear_buffer(val=" ")
            self.scene.draw(self._screen)
            self.frame.draw(buffer, self._screen)
            self._draw_labels(buffer)

    def _draw_labels(self, buffer: Buffer) -> None:
        label = self.phases[self.index][0]
        title = f"Audio {self.index + 1}/{len(self.phases)}: {label} | {self.bindings.help_text()}"
        buffer.put_at(0, 0, title.ljust(buffer.width()))
        if buffer.height() > 1:
            error = getattr(self.phases[self.index][1], "_error", None)
            buffer.put_at(
                0,
                buffer.height() - 1,
                (error or MODE_HELP[label]).ljust(buffer.width()),
            )


def build(buffer: Buffer, *, computer: ComputerStyle = "classic") -> AudioShowcase:
    """Build inert audio modes with snow behind classic, expanded, or box artwork.

    Classic/expanded fall back to box below 67x32. C cycles classic, expanded,
    box; arrows select audio. Snow runs at 15 updates/sec across mode changes.
    Every audio buffer fits the monitor opening, not the terminal.
    """
    size = (buffer.width(), buffer.height())
    frame = ComputerFrame(size, computer)
    phases = [
        ("Objects", AudioSettings(mode="objects")),
        ("Tiles", AudioSettings(mode="tiles", smoothing=0.75)),
        ("Glow", AudioSettings(mode="glow", smoothing=0.8)),
        ("Bars", AudioSettings(mode="bars", bar_char="#", smoothing=0.7, compact=True)),
        (
            "Mirror",
            AudioSettings(mode="mirror", bar_char="#", smoothing=0.7, compact=True),
        ),
        ("Waveform", AudioSettings(mode="waveform", smoothing=0.6)),
        ("Spectrum", AudioSettings(mode="spectrum", smoothing=0.4)),
    ]
    return AudioShowcase(
        [
            (
                label,
                effect_registry.create(
                    "audio",
                    Buffer(frame.screen_size[1], frame.screen_size[0]),
                    " ",
                    settings=config,
                ),
            )
            for label, config in phases
        ],
        size=size,
        computer=computer,
    )


def run(
    *,
    frames: int | None = None,
    fps: float = TARGET_FPS,
    on_resize: ResizePolicy = "resize",
    computer: ComputerStyle = "classic",
) -> int:
    """Play system audio; left/right wrap modes, with no automatic cycling.

    C cycles classic/expanded/box without restarting capture or snow. q/Q, Escape and Ctrl+C
    quit. Resize preserves the selected mode and animation state.
    Player owns the showcase; switching closes the old capture before starting
    the new one. Constructors and zero-frame runs do not open audio devices.
    """
    showcase: Showcase | None = None

    def create(buffer: Buffer) -> Showcase:
        nonlocal showcase
        showcase = build(buffer, computer=computer)
        return showcase

    def handle_event(event: int) -> bool:
        assert showcase is not None  # Player creates/starts content before polling.
        return showcase.handle_event(event)

    return play(
        effect_factory=create,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        on_resize=on_resize,
        event_handler=handle_event,
    )


if __name__ == "__main__":
    run()
