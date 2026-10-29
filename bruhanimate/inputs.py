"""Focusable single-cell text editing and form controls, without input polling."""

from collections.abc import Callable

from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .keyboard import EventResult, FocusTarget, KeyBindings
from .resize import _size
from .styling import TextStyle
from .widgets import _validate_text


class _InputControl:
    def __init__(self, name: str, *, enabled: bool, style: TextStyle | None) -> None:
        if style is not None and not isinstance(style, TextStyle):
            raise TypeError("style must be a TextStyle or None")
        self._style = style or TextStyle()
        self._started = self._closed = False
        self._visible = True
        self._focus = FocusTarget(
            name, KeyBindings(), enabled=enabled, handler=self._dispatch
        )
        self._focus._attach(self)

    @property
    def focus(self) -> FocusTarget:
        """Owned target for a FocusGroup; do not also attach it to a Panel."""
        return self._focus

    @property
    def enabled(self) -> bool:
        return self.focus.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.focus.enabled = value

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("control is closed; construct a new instance")
        self._started = True
        self.focus._activate(self._visible)

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started or self._closed:
            raise RuntimeError("control must be started and not closed")

    def resize(self, size: tuple[int, int]) -> None:
        """Keep edit state; drawing adapts to its current local buffer width."""
        _size(size)

    def set_visible(self, visible: bool) -> None:
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        self._visible = visible
        self.focus._activate(visible and self._started and not self._closed)

    def _dispatch(self, event: int) -> EventResult:
        if not self.focus.focused or not self.focus.available:
            return EventResult.UNHANDLED
        return self._edit(event)

    def _edit(self, event: int) -> EventResult:
        raise NotImplementedError

    def _paint(self, buffer: Buffer, text: str) -> None:
        if self._closed or not self._visible or buffer.height() == 0:
            return
        for x in range(buffer.width()):
            buffer.put_char(x, 0, self._style._cell(text[x] if x < len(text) else " "))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.focus._detach()


class TextInput(_InputControl):
    """Single-line insert-mode editor with an owned FocusTarget and bounded text.

    Left/right/home/end move the cursor; backspace/delete edit; Enter invokes
    on_submit. Printable single-cell characters, including q and space, insert
    at the cursor. Unsupported keys fall through to scope bindings. Tab belongs
    to FocusGroup. No multiline, selection, paste protocol, mouse or IME support.

    Events edit immediately on the playback thread; on_change runs after an
    actual change, and on_submit receives current text. Programmatic value
    assignment validates atomically, moves the cursor to the end and notifies
    on_change only if changed. Construction never invokes callbacks. Callbacks
    may enqueue application actions; exceptions propagate to Player cleanup.

    Draw paints one local row and scrolls to a plain '|' caret while focused,
    without changing cursor/value or invoking callbacks. The caret is display
    only. Resize retains edits; hidden/disabled/closed controls are not eligible
    for focus. Own the control through Scene/Panel/layout; register its .focus
    in one FocusGroup. Never pass that same target as Panel(focus=...).
    """

    def __init__(
        self,
        name: str,
        value: str = "",
        *,
        max_length: int = 256,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        enabled: bool = True,
        style: TextStyle | None = None,
    ) -> None:
        if type(max_length) is not int or max_length < 0:
            raise ValueError("max_length must be a non-negative integer")
        for callback in (on_change, on_submit):
            if callback is not None and not callable(callback):
                raise TypeError("callbacks must be callable or None")
        self._max_length = max_length
        self._validate(value)
        self._value, self._cursor = value, len(value)
        self._on_change, self._on_submit = on_change, on_submit
        super().__init__(name, enabled=enabled, style=style)

    def _validate(self, value: str) -> None:
        _validate_text(value, multiline=False)
        if len(value) > self._max_length:
            raise ValueError("value exceeds max_length")

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self._validate(value)
        self._commit(value, len(value))

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def max_length(self) -> int:
        return self._max_length

    def _commit(self, value: str, cursor: int) -> None:
        changed = value != self._value
        self._value, self._cursor = value, cursor
        if changed and self._on_change is not None:
            self._on_change(value)

    def _edit(self, event: int) -> EventResult:
        value, cursor = self.value, self.cursor
        if event == -203:
            self._cursor = max(0, cursor - 1)
        elif event == -205:
            self._cursor = min(len(value), cursor + 1)
        elif event == -200:
            self._cursor = 0
        elif event == -201:
            self._cursor = len(value)
        elif event == -300:
            if cursor:
                self._commit(value[: cursor - 1] + value[cursor:], cursor - 1)
        elif event == -102:
            if cursor < len(value):
                self._commit(value[:cursor] + value[cursor + 1 :], cursor)
        elif event == 10:
            if self._on_submit is not None:
                self._on_submit(value)
        elif 0 <= event <= 0x10FFFF:
            char = chr(event)
            try:
                _validate_text(char, multiline=False)
            except ValueError:
                return EventResult.UNHANDLED
            if len(value) < self.max_length:
                self._commit(value[:cursor] + char + value[cursor:], cursor + 1)
        else:
            return EventResult.UNHANDLED
        return EventResult.HANDLED

    def draw(self, buffer: Buffer) -> None:
        text = self.value
        if self.focus.focused:
            text = text[: self.cursor] + "|" + text[self.cursor :]
            offset = max(0, self.cursor - max(1, buffer.width()) + 1)
            text = text[offset:]
        self._paint(buffer, text)


class Checkbox(_InputControl):
    """One-row boolean editor; Space/Enter toggles and notifies on_change.

    Owns .focus, has no resource side effects and follows TextInput's lifecycle.
    checked assignments validate before mutation and notify only on change.
    Draw uses '[x]'/'[ ]' and a leading '>' when focused, even without color.
    """

    def __init__(
        self,
        name: str,
        label: str,
        *,
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        enabled: bool = True,
        style: TextStyle | None = None,
    ) -> None:
        _validate_text(label, multiline=False)
        if type(checked) is not bool:
            raise TypeError("checked must be a bool")
        if on_change is not None and not callable(on_change):
            raise TypeError("on_change must be callable or None")
        self._label, self._checked, self._on_change = label, checked, on_change
        super().__init__(name, enabled=enabled, style=style)

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("checked must be a bool")
        if value != self._checked:
            self._checked = value
            if self._on_change is not None:
                self._on_change(value)

    def _edit(self, event: int) -> EventResult:
        if event not in (10, 32):
            return EventResult.UNHANDLED
        self.checked = not self.checked
        return EventResult.HANDLED

    def draw(self, buffer: Buffer) -> None:
        marker = ">" if self.focus.focused else " "
        self._paint(buffer, f"{marker} [{'x' if self.checked else ' '}] {self._label}")


class Button(_InputControl):
    """One-row Space/Enter action, with an owned .focus target.

    The action runs only on dispatched activation, never start/update/draw.
    It must return None; use scope bindings with quit=True to request exit.
    Lifecycle, visibility and ownership match TextInput.
    """

    def __init__(
        self,
        name: str,
        label: str,
        action: Callable[[], None],
        *,
        enabled: bool = True,
        style: TextStyle | None = None,
    ) -> None:
        _validate_text(label, multiline=False)
        if not callable(action):
            raise TypeError("action must be callable")
        self._label, self._action = label, action
        super().__init__(name, enabled=enabled, style=style)

    def _edit(self, event: int) -> EventResult:
        if event not in (10, 32):
            return EventResult.UNHANDLED
        if self._action() is not None:
            raise TypeError("Button action must return None")
        return EventResult.HANDLED

    def draw(self, buffer: Buffer) -> None:
        marker = ">" if self.focus.focused else " "
        self._paint(buffer, f"{marker} [ {self._label} ]")
