"""An in-memory settings form demonstrating modal focus and editable controls.

E opens settings. Tab/Shift+Tab navigates. Enter/Space activates buttons and
checkboxes; text input inserts printable keys. Escape cancels the modal, Ctrl+C
quits. Q quits only from the main screen; in the name field it is ordinary text.
Nothing is saved to disk or sent anywhere.
"""

from contextlib import ExitStack

from bruhanimate import (
    Buffer,
    Button,
    Checkbox,
    Column,
    Fixed,
    FocusGroup,
    FocusStack,
    KeyBinding,
    KeyBindings,
    Label,
    ResizePolicy,
    Row,
    Slot,
    Spacer,
    TextInput,
    TextStyle,
    play,
)
from bruhanimate._validation import _seconds
from bruhanimate.keyboard import _set_visible


class SettingsDemo:
    def __init__(self, buffer: Buffer) -> None:
        self.name = "Explorer"
        self.effects_enabled = True
        self.background_actions = 0
        self.message = ""
        self.modal_open = False
        self._visible = True
        self._started = self._closed = False
        self.edit = Button("edit", "Edit settings", self.open_modal)
        self.count = Button("count", "Background action", self.increment)
        self.name_input = TextInput(
            "name", self.name, max_length=32, on_submit=lambda value: self.apply()
        )
        self.effects = Checkbox("effects", "Enable effects", checked=True)
        self.apply_button = Button("apply", "Apply", self.apply)
        self.cancel_button = Button("cancel", "Cancel", self.cancel)
        self.root_scope = FocusGroup(
            self.edit.focus,
            self.count.focus,
            global_bindings=KeyBindings(
                KeyBinding.character("e", self.open_modal),
                KeyBinding.character("b", self.increment),
                KeyBinding.character("q", quit=True),
                KeyBinding.character("Q", quit=True),
                KeyBinding("escape", quit=True),
                KeyBinding("ctrl+c", quit=True),
            ),
        )
        self.modal_scope = FocusGroup(
            self.name_input.focus,
            self.effects.focus,
            self.apply_button.focus,
            self.cancel_button.focus,
            global_bindings=KeyBindings(
                KeyBinding("escape", self.cancel), KeyBinding("ctrl+c", quit=True)
            ),
        )
        self.focus = FocusStack(self.root_scope)
        self.main = Column(
            Slot(
                Label("TUI SETTINGS", style=TextStyle(foreground=117, bold=True)),
                size=Fixed(1),
            ),
            Slot(
                Label(
                    lambda: f"Name: {self.name}\nEffects: {'on' if self.effects_enabled else 'off'}"
                ),
                size=Fixed(2),
            ),
            Slot(self.edit, size=Fixed(1)),
            Slot(self.count, size=Fixed(1)),
            Slot(
                Label(lambda: f"Background actions: {self.background_actions}"),
                size=Fixed(1),
            ),
            Spacer(),
            Slot(
                Label("e edit | Tab navigate | Enter activate | q quit"), size=Fixed(1)
            ),
            padding=1,
            gap=1,
        ).build(buffer)
        self.dialog = Column(
            Slot(
                Label("EDIT SETTINGS", style=TextStyle(foreground=229, bold=True)),
                size=Fixed(1),
            ),
            Slot(Label("Name (32 cells maximum)"), size=Fixed(1)),
            Slot(self.name_input, size=Fixed(1)),
            Slot(self.effects, size=Fixed(1)),
            Slot(
                Row(Slot(self.apply_button), Slot(self.cancel_button), gap=2),
                size=Fixed(1),
            ),
            Slot(
                Label(lambda: self.message, style=TextStyle(foreground=203)),
                size=Fixed(1),
            ),
            Spacer(),
            Slot(
                Label(
                    "Tab/Shift+Tab navigate | Enter apply | Esc cancel\nPrintable keys edit the name, including q. Ctrl+C quits."
                ),
                size=Fixed(2),
            ),
            padding=1,
            gap=1,
            background=" ",
        ).build(buffer)
        _set_visible(self.dialog, False)

    def increment(self) -> None:
        self.background_actions += 1

    def open_modal(self) -> None:
        if self.modal_open or self._closed:
            return
        self.name_input.value = self.name
        self.effects.checked = self.effects_enabled
        self.message = ""
        _set_visible(self.dialog, self._visible)
        self.focus.push(self.modal_scope)
        self.modal_open = True
        self.modal_scope.focus("name")

    def cancel(self) -> None:
        if self.modal_open:
            _set_visible(self.dialog, False)
            self.focus.pop()
            self.modal_open = False

    def apply(self) -> None:
        if not self.modal_open:
            return
        if not self.name_input.value.strip():
            self.message = "Enter a nonblank name."
            self.modal_scope.focus("name")
            return
        self.name = self.name_input.value
        self.effects_enabled = self.effects.checked
        self.cancel()

    def handle_event(self, code: int) -> bool:
        return self.focus.handle_event(code)

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("settings demo is closed")
        if not self._started:
            self._started = True
            try:
                self.main.start()
                self.dialog.start()
            except BaseException:
                self.close()
                raise

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        self.main.update(dt)
        self.dialog.update(dt)

    def resize(self, size: tuple[int, int]) -> None:
        self.main.resize(size)
        self.dialog.resize(size)

    def set_visible(self, visible: bool) -> None:
        _set_visible(self.main, visible)
        _set_visible(self.dialog, visible and self.modal_open)
        self._visible = visible

    def draw(self, buffer: Buffer) -> None:
        if self._visible:
            self.main.draw(buffer)
            if self.modal_open:
                self.dialog.draw(buffer)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.focus.close()
            with ExitStack() as cleanup:
                cleanup.callback(self.main.close)
                cleanup.callback(self.dialog.close)


def build(buffer: Buffer) -> SettingsDemo:
    return SettingsDemo(buffer)


def run(
    *, frames: int | None = None, fps: float = 30, on_resize: ResizePolicy = "resize"
) -> int:
    demo: SettingsDemo | None = None

    def factory(buffer: Buffer) -> SettingsDemo:
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
