"""Pause/step and scale a tick-based snow field and a continuous moving sprite.

Space pauses/resumes; N steps while pausing; 1/2/3 select half/normal/double speed;
0 freezes time scale and Q quits. Commands apply only during updates.
"""

from bruhanimate import (
    ActionQueue,
    AnimationControl,
    Buffer,
    KeyBinding,
    KeyBindings,
    ResizePolicy,
    SnowEffect,
    SnowSettings,
    Sprite,
    SpriteAsset,
    play,
)
from bruhanimate._validation import _seconds
from bruhanimate.resize import _size


class ControlsDemo:
    def __init__(self, buffer: Buffer) -> None:
        self.size = (buffer.width(), buffer.height())
        self.snow = AnimationControl(
            SnowEffect(buffer, " ", SnowSettings(seed=7, intensity=0.1)),
            mode="fixed",
        )
        self.marker = Sprite(
            SpriteAsset.from_text("<o>"),
            position=(0, buffer.height() // 2),
            velocity=(6, 0),
        )
        self.motion = AnimationControl(self.marker, mode="continuous")
        self.actions: ActionQueue[str] = ActionQueue(capacity=32)
        self.bindings = KeyBindings(
            KeyBinding("space", self.actions.bind("pause")),
            KeyBinding.character("n", self.actions.bind("step")),
            *(KeyBinding.character(key, self.actions.bind(key)) for key in "0123"),
            KeyBinding.character("q", quit=True),
            KeyBinding.character("Q", quit=True),
            KeyBinding("escape", quit=True),
            KeyBinding("ctrl+c", quit=True),
        )
        self._started = self._closed = False

    def handle_event(self, code: int) -> bool:
        return self.bindings.handle_event(code) if not self._closed else False

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("demo is closed")
        if not self._started:
            self._started = True
            try:
                self.snow.start()
                self.motion.start()
            except BaseException:
                self.close()
                raise

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started or self._closed:
            raise RuntimeError("demo must be started and not closed")
        for action in self.actions.drain(limit=8):
            for control in (self.snow, self.motion):
                if action == "pause":
                    control.toggle_pause()
                elif action == "step":
                    control.pause()
                    control.step()
                else:
                    control.time_scale = {"0": 0, "1": 0.5, "2": 1, "3": 2}[action]
        self.snow.update(dt)
        self.motion.update(dt)
        self.marker.position = (
            self.marker.position[0] % self.size[0],
            self.marker.position[1],
        )

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self.snow.resize(size)
        self.motion.resize(size)
        self.size = size
        self.marker.position = (self.marker.position[0], size[1] // 2)

    def draw(self, buffer: Buffer) -> None:
        self.snow.draw(buffer)
        self.motion.draw(buffer)
        state = "PAUSED" if self.motion.paused else "RUN"
        buffer.put_at(
            0,
            0,
            f"{state} {self.motion.time_scale:g}x | fixed snow + continuous sprite".ljust(
                buffer.width()
            ),
        )
        if buffer.height() > 1:
            help_text = "space pause | n step | 0 freeze | 1/2/3 speed | q quit"
            if buffer.width() < len(help_text):
                help_text = "space/n 0/1/2/3 q:quit"
            buffer.put_at(0, buffer.height() - 1, help_text.ljust(buffer.width()))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.actions.clear()
            try:
                self.motion.close()
            finally:
                self.snow.close()


def build(buffer: Buffer) -> ControlsDemo:
    return ControlsDemo(buffer)


def run(
    *, frames: int | None = None, fps: float = 30, on_resize: ResizePolicy = "resize"
) -> int:
    demo: ControlsDemo | None = None

    def factory(buffer: Buffer) -> ControlsDemo:
        nonlocal demo
        demo = build(buffer)
        return demo

    def event(code: int) -> bool:
        return demo.handle_event(code) if demo is not None else False

    return play(
        effect_factory=factory,
        event_handler=event,
        frames=frames,
        fps=fps,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
