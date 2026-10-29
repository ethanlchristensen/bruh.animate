"""Declarative keyboard routing; no input polling or animation ownership."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .grid import _glyph

KeyName = Literal[
    "space",
    "enter",
    "escape",
    "tab",
    "shift+tab",
    "backspace",
    "delete",
    "insert",
    "home",
    "end",
    "left",
    "right",
    "up",
    "down",
    "page_up",
    "page_down",
    "ctrl+c",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
]
FocusDirection = Literal["next", "previous"]
_CODES: dict[str, int] = {
    "space": 32,
    "enter": 10,
    "escape": -1,
    "tab": -301,
    "shift+tab": -302,
    "backspace": -300,
    "delete": -102,
    "insert": -101,
    "home": -200,
    "end": -201,
    "left": -203,
    "right": -205,
    "up": -204,
    "down": -206,
    "page_up": -207,
    "page_down": -208,
    "ctrl+c": 3,
    **{f"f{i}": -1 - i for i in range(1, 13)},
}


def _event(code: int) -> int:
    if type(code) is not int:
        raise TypeError("key events must be integers")
    return {27: -1, 13: 10, 9: -301, 11: -301, 8: -300, 127: -300}.get(code, code)


def _text(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("names and descriptions must be strings")
    for char in value:
        _glyph(char)


class EventResult(Enum):
    """Dispatch result; use handle_event with Player, never enum truthiness."""

    UNHANDLED = "unhandled"
    HANDLED = "handled"
    QUIT = "quit"

    def __bool__(self) -> bool:
        raise TypeError("Compare EventResult explicitly; pass handle_event to Player")


@dataclass(frozen=True)
class BindingHint:
    """A displayable key/description pair for a help label or status bar."""

    key: str
    description: str


class KeyBinding:
    """Bind a Literal-typed named key to a zero-argument action.

    Use character() for a single printable character, e.g. 'q' or '+'. Actions
    return None; any matched binding consumes the event. quit=True requests exit
    after its optional action. Empty descriptions omit aliases from help text.
    Construction never calls actions or opens a terminal.
    """

    def __init__(
        self,
        key: KeyName,
        action: Callable[[], None] | None = None,
        *,
        description: str = "",
        quit: bool = False,
    ) -> None:
        if key not in _CODES:
            raise ValueError(
                "Unknown named key; use KeyBinding.character for text keys"
            )
        self._configure(_CODES[key], key, action, description, quit)

    def _configure(
        self,
        code: int,
        key: str,
        action: Callable[[], None] | None,
        description: str,
        quit: bool,
    ) -> None:
        _text(description)
        if type(quit) is not bool:
            raise TypeError("quit must be a bool")
        if action is not None and not callable(action):
            raise TypeError("action must be callable or None")
        if action is None and not quit:
            raise ValueError("A binding needs an action or quit=True")
        self._code, self._key = code, key
        self._action, self._description, self._quit = action, description, quit

    @classmethod
    def character(
        cls,
        character: str,
        action: Callable[[], None] | None = None,
        *,
        description: str = "",
        quit: bool = False,
    ) -> KeyBinding:
        """Bind one printable single-cell character; matching is case-sensitive."""
        if not isinstance(character, str) or len(character) != 1:
            raise ValueError("character must be one printable single-cell character")
        _glyph(character)
        binding = cls.__new__(cls)
        binding._configure(ord(character), character, action, description, quit)
        return binding

    @property
    def key(self) -> str:
        return self._key

    @property
    def description(self) -> str:
        return self._description

    def _invoke(self) -> EventResult:
        if self._action is not None and self._action() is not None:
            raise TypeError("Binding actions must return None; use quit=True to exit")
        return EventResult.QUIT if self._quit else EventResult.HANDLED


class KeyBindings:
    """An ordered, immutable set of bindings; duplicate normalized keys are errors.

    dispatch returns EventResult for composition. handle_event adapts to Player's
    bool contract (True only for quit). No default keys are installed here.
    """

    def __init__(self, *bindings: KeyBinding) -> None:
        if any(not isinstance(binding, KeyBinding) for binding in bindings):
            raise TypeError("KeyBindings requires KeyBinding instances")
        codes = [binding._code for binding in bindings]
        if len(set(codes)) != len(codes):
            raise ValueError("Duplicate key binding")
        self._bindings = bindings
        self._lookup = dict(zip(codes, bindings))

    @property
    def bindings(self) -> tuple[KeyBinding, ...]:
        return self._bindings

    def hints(self) -> tuple[BindingHint, ...]:
        """Descriptions in declaration order, omitting undescribed aliases."""
        return tuple(
            BindingHint(b.key, b.description) for b in self._bindings if b.description
        )

    def help_text(self, separator: str = " | ") -> str:
        """Format declarative hints; never invoke actions."""
        return separator.join(f"{hint.key} {hint.description}" for hint in self.hints())

    def dispatch(self, event: int) -> EventResult:
        binding = self._lookup.get(_event(event))
        return binding._invoke() if binding is not None else EventResult.UNHANDLED

    def handle_event(self, event: int) -> bool:
        """Player-compatible handler; handled actions never accidentally quit."""
        return self.dispatch(event) is EventResult.QUIT


class FocusTarget:
    """Bindings and focus state for one Panel/control, in one FocusGroup.

    A target becomes eligible when its panel starts and is visible. enabled=False
    excludes it without pausing its animation. The group borrows targets; neither
    targets nor groups start/close content. Never attach a target to two owners.
    An optional handler receives keys not matched by bindings and must return
    EventResult. FocusGroup still reserves its navigation keys before dispatch.
    """

    def __init__(
        self,
        name: str,
        bindings: KeyBindings,
        *,
        enabled: bool = True,
        handler: Callable[[int], EventResult] | None = None,
    ) -> None:
        _text(name)
        if not name:
            raise ValueError("Focus target names must be nonempty")
        if not isinstance(bindings, KeyBindings):
            raise TypeError("bindings must be KeyBindings")
        if type(enabled) is not bool:
            raise TypeError("enabled must be a bool")
        if handler is not None and not callable(handler):
            raise TypeError("handler must be callable or None")
        self._handler = handler
        self._name, self._bindings, self._enabled = name, bindings, enabled
        self._active = self._focused = False
        self._owner: object | None = None
        self._group: FocusGroup | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def bindings(self) -> KeyBindings:
        return self._bindings

    @property
    def focused(self) -> bool:
        """Read-only selection state; reading/drawing never changes focus."""
        return self._focused

    @property
    def available(self) -> bool:
        return self._active and self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("enabled must be a bool")
        self._enabled = value
        self._refresh()

    def _refresh(self) -> None:
        if self._group is not None:
            self._group._reconcile()

    def _dispatch(self, event: int) -> EventResult:
        result = self.bindings.dispatch(event)
        if result is EventResult.UNHANDLED and self._handler is not None:
            result = self._handler(event)
            if not isinstance(result, EventResult):
                raise TypeError("FocusTarget handler must return EventResult")
        return result

    def _attach(self, owner: object) -> None:
        if self._owner is not None:
            raise ValueError("A FocusTarget can belong to only one panel/control")
        self._owner = owner

    def _activate(self, active: bool) -> None:
        self._active = active
        self._refresh()

    def _detach(self) -> None:
        self._owner = None
        self._activate(False)


class FocusGroup:
    """Route navigation, then focused bindings, then application bindings.

    Pass handle_event to Player. Tab/Shift+Tab are reserved navigation by default;
    override next_key/previous_key with typed key names. Focus wraps by default.
    Unhandled q/Q, Escape and Ctrl+C quit unless global_bindings is supplied.
    Local bindings/handlers can consume those keys first. Hidden/disabled/closed targets
    are skipped. Showing a panel does not steal focus from an eligible selection.
    No terminal polling, simulation advancement, or child ownership occurs here.
    """

    def __init__(
        self,
        *targets: FocusTarget,
        global_bindings: KeyBindings | None = None,
        next_key: KeyName = "tab",
        previous_key: KeyName = "shift+tab",
        wrap: bool = True,
    ) -> None:
        if any(not isinstance(target, FocusTarget) for target in targets):
            raise TypeError("FocusGroup requires FocusTarget instances")
        if len({t.name for t in targets}) != len(targets):
            raise ValueError("Focus target names must be unique")
        if any(t._group is not None for t in targets):
            raise ValueError("A FocusTarget can belong to only one group")
        if next_key not in _CODES or previous_key not in _CODES:
            raise ValueError("Navigation requires named keys")
        if next_key == previous_key:
            raise ValueError("Navigation keys must differ")
        if type(wrap) is not bool:
            raise TypeError("wrap must be a bool")
        if global_bindings is not None and not isinstance(global_bindings, KeyBindings):
            raise TypeError("global_bindings must be KeyBindings or None")
        self._targets, self._wrap = targets, wrap
        self._next, self._previous = _CODES[next_key], _CODES[previous_key]
        self._global = (
            global_bindings
            if global_bindings is not None
            else KeyBindings(
                KeyBinding.character("q", quit=True, description="quit"),
                KeyBinding.character("Q", quit=True),
                KeyBinding("escape", quit=True),
                KeyBinding("ctrl+c", quit=True),
            )
        )
        self._focused: FocusTarget | None = None
        self._suspended = False
        self._saved_focus: FocusTarget | None = None
        self._stack: FocusStack | None = None
        for target in targets:
            target._group = self
        self._reconcile()

    @property
    def focused(self) -> FocusTarget | None:
        return self._focused

    @property
    def targets(self) -> tuple[FocusTarget, ...]:
        return self._targets

    def _select(self, target: FocusTarget | None) -> None:
        if self._focused is not None:
            self._focused._focused = False
        self._focused = target
        if target is not None:
            target._focused = True

    def _reconcile(self) -> None:
        if self._suspended:
            self._select(None)
            return
        if self._focused is not None and self._focused.available:
            return
        start = (
            self._targets.index(self._focused) + 1 if self._focused is not None else 0
        )
        ordered = self._targets[start:] + self._targets[:start]
        self._select(next((t for t in ordered if t.available), None))

    def _suspend(self, suspended: bool) -> None:
        if suspended == self._suspended:
            return
        self._suspended = suspended
        if suspended:
            self._saved_focus = self._focused
            self._select(None)
        else:
            saved, self._saved_focus = self._saved_focus, None
            if saved is not None and saved.available:
                self._select(saved)
            else:
                self._reconcile()

    def focus(self, name: str) -> bool:
        """Select a named eligible target; False if hidden/disabled, KeyError if unknown."""
        for target in self._targets:
            if target.name == name:
                if target.available and not self._suspended:
                    self._select(target)
                    return True
                return False
        raise KeyError(name)

    def move(self, direction: FocusDirection = "next") -> None:
        """Move in declaration order, skipping unavailable targets."""
        if direction not in ("next", "previous"):
            raise ValueError("direction must be next or previous")
        if self._suspended:
            return
        available = [target for target in self._targets if target.available]
        if not available:
            return
        index = available.index(self._focused) if self._focused in available else 0
        index += 1 if direction == "next" else -1
        index = (
            index % len(available)
            if self._wrap
            else max(0, min(len(available) - 1, index))
        )
        self._select(available[index])

    def help_text(self) -> str:
        """Current target's hints for an update-time StatusBar callback."""
        return self._focused.bindings.help_text() if self._focused is not None else ""

    def dispatch(self, event: int) -> EventResult:
        code = _event(event)
        if self._suspended:
            return EventResult.UNHANDLED
        if code in (self._next, self._previous):
            self.move("next" if code == self._next else "previous")
            return EventResult.HANDLED
        if self._focused is not None:
            result = self._focused._dispatch(code)
            if result is not EventResult.UNHANDLED:
                return result
            # A custom handler may push a modal and still return UNHANDLED.
            # Do not run the now-suspended scope's global shortcut afterward.
            if self._suspended:
                return EventResult.HANDLED
        return self._global.dispatch(code)

    def handle_event(self, event: int) -> bool:
        """Return True only for quit, matching Player's event_handler contract."""
        return self.dispatch(event) is EventResult.QUIT


class FocusStack:
    """Borrow a root FocusGroup and nested modal groups; route only to the top.

    Push suspends lower groups, including their global shortcuts and focus
    highlights. Pop restores the previous target if still eligible, otherwise
    the first eligible target. Unhandled modal keys are consumed, preventing
    caller fallback into background controls. No automatic Escape/quit policy is
    installed: configure each group's global bindings explicitly.

    This router does not own, start, hide or close animations. Hide/close modal
    content before popping its group. A popped group becomes standalone again;
    its own eligible target may regain focus. Groups cannot be in two stacks or
    pushed twice. Close releases all borrowed groups to standalone operation,
    never closes their controls, and makes this stack unusable for further input.
    """

    def __init__(self, root: FocusGroup) -> None:
        self._validate(root)
        self._groups = [root]
        self._closed = False
        root._stack = self

    @staticmethod
    def _validate(group: FocusGroup) -> None:
        if not isinstance(group, FocusGroup):
            raise TypeError("scope must be a FocusGroup")
        if group._stack is not None:
            raise ValueError("FocusGroup already belongs to a stack")

    @property
    def active(self) -> FocusGroup | None:
        return self._groups[-1] if self._groups else None

    @property
    def depth(self) -> int:
        return len(self._groups)

    def push(self, group: FocusGroup) -> None:
        if self._closed:
            raise RuntimeError("FocusStack is closed")
        self._validate(group)
        self._groups[-1]._suspend(True)
        group._stack = self
        self._groups.append(group)

    def pop(self) -> FocusGroup:
        """Release the top modal scope; the root cannot be popped."""
        if self._closed or len(self._groups) < 2:
            raise RuntimeError("no modal scope to pop")
        removed = self._groups.pop()
        removed._stack = None
        self._groups[-1]._suspend(False)
        return removed

    def dispatch(self, event: int) -> EventResult:
        if self._closed:
            raise RuntimeError("FocusStack is closed")
        modal = self.depth > 1
        result = self._groups[-1].dispatch(event)
        if result is EventResult.UNHANDLED and (modal or self.depth > 1):
            return EventResult.HANDLED
        return result

    def handle_event(self, event: int) -> bool:
        return self.dispatch(event) is EventResult.QUIT

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            groups, self._groups = self._groups, []
            for group in reversed(groups):
                group._stack = None
                group._suspend(False)


def _set_visible(animation: object, visible: bool) -> None:
    """Propagate layout visibility without input polling or lifecycle changes."""
    notify = getattr(animation, "set_visible", None)
    if notify is not None:
        notify(visible)
