"""Owned, ordered animation groups with deferred membership changes."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack
from typing import Literal

from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .keyboard import _set_visible
from .player import Animation
from .resize import _resize, _size


class ObjectGroup:
    """Own animations under stable names and compose them in insertion order.

    Successful add immediately transfers ownership, including pending children.
    Add/remove/move_to_end commands apply at start and at the beginning of each
    update. Commands made by child callbacks wait until the next update; they
    never mutate the iteration in progress. Names/get expose applied membership.
    Validation uses projected membership, so queued duplicate names are rejected.
    A pending removal's instance cannot be added again until removal is applied.

    New children receive the latest viewport and visibility before start, then
    the current update's full dt. Removed children close before that update and
    never update/draw again. Cleanup closes all still-owned children in reverse
    acquisition order, even before start or after partial startup. Membership
    application failures close the whole group; close is idempotent, even when a
    child close raises. Instances must not also belong to another owner.

    Drawing isolates each child on one reusable scratch surface, then paints
    non-None cells in order; plain spaces paint. Use Scene/Layer inside a child
    for masks, styles or space transparency. Resize retains children and clocks.
    Hidden groups still update. Groups report finished=None, including when empty;
    remove finite children explicitly. Route input explicitly via Player.
    """

    def __init__(self, children: Mapping[str, Animation] | None = None) -> None:
        # Validate the entire initial set before accepting ownership.
        initial = dict(children) if children is not None else {}
        seen: set[int] = set()
        for name, animation in initial.items():
            self._validate_child(name, animation)
            if id(animation) in seen:
                raise ValueError("cannot own the same animation twice")
            seen.add(id(animation))
        self._active: dict[str, Animation] = {}
        self._projected: dict[str, Animation] = {}
        self._owned: dict[int, Animation] = {}
        self._pending: list[
            tuple[Literal["add", "remove", "move"], str, Animation | None]
        ] = []
        self._started = self._closed = False
        self._visible = True
        self._size: tuple[int, int] | None = None
        self._scratch: Buffer | None = None
        for name, animation in initial.items():
            self.add(name, animation)

    @staticmethod
    def _validate_child(name: str, animation: Animation) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("object name must be a non-empty string")
        if not isinstance(animation, Animation):
            raise TypeError("ObjectGroup children must implement Animation")

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("ObjectGroup is single-use; construct a new instance")

    @property
    def names(self) -> tuple[str, ...]:
        """Applied names in paint order; pending commands are not included."""
        return tuple(self._active)

    @property
    def finished(self) -> None:
        return None

    def get(self, name: str) -> Animation:
        """Borrow an applied child without transferring ownership; KeyError if absent."""
        return self._active[name]

    def add(self, name: str, animation: Animation) -> None:
        """Queue a fresh owned child; names and instances must be unique."""
        self._check_open()
        self._validate_child(name, animation)
        if animation is self:
            raise ValueError("a group cannot own itself")
        if name in self._projected:
            raise ValueError(f"object name already exists: {name!r}")
        if id(animation) in self._owned:
            raise ValueError("cannot own the same animation twice")
        self._projected[name] = animation
        self._owned[id(animation)] = animation
        self._pending.append(("add", name, animation))

    def remove(self, name: str) -> None:
        """Queue removal and close; KeyError if absent from projected membership."""
        self._check_open()
        del self._projected[name]
        self._pending.append(("remove", name, None))

    def move_to_end(self, name: str) -> None:
        """Queue painting a child last, without restarting it or changing cleanup order."""
        self._check_open()
        child = self._projected.pop(name)
        self._projected[name] = child
        self._pending.append(("move", name, None))

    def _apply_pending(self) -> None:
        commands, self._pending = self._pending, []
        try:
            for operation, name, animation in commands:
                if operation == "add":
                    assert animation is not None
                    self._active[name] = animation
                    if self._size is not None:
                        _resize(animation, self._size)
                    _set_visible(animation, self._visible)
                    animation.start()
                elif operation == "remove":
                    removed = self._active.pop(name)
                    del self._owned[id(removed)]
                    removed.close()
                else:
                    moved = self._active.pop(name)
                    self._active[name] = moved
        except BaseException:
            self.close()
            raise

    def start(self) -> None:
        self._check_open()
        if not self._started:
            self._started = True
            self._apply_pending()

    def update(self, dt: float) -> None:
        self._check_open()
        if not self._started:
            raise RuntimeError("ObjectGroup must be started before update")
        _seconds(dt, "dt")
        self._apply_pending()
        for animation in tuple(self._active.values()):
            animation.update(dt)

    def set_visible(self, visible: bool) -> None:
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        self._visible = visible
        for animation in tuple(self._active.values()):
            _set_visible(animation, visible)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self._size = size
        self._scratch = None
        for animation in tuple(self._active.values()):
            _resize(animation, size)

    def draw(self, buffer: Buffer) -> None:
        if not self._visible or self._closed:
            return
        size = (buffer.height(), buffer.width())
        if (
            self._scratch is None
            or (self._scratch.height(), self._scratch.width()) != size
        ):
            self._scratch = Buffer(*size)
        for animation in tuple(self._active.values()):
            self._scratch.clear_buffer(val=None)
            animation.draw(self._scratch)
            for row, source in enumerate(self._scratch.buffer):
                for column, cell in enumerate(source):
                    if cell is not None:
                        buffer.put_char(column, row, str(cell))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        owned, self._owned = self._owned, {}
        self._active.clear()
        self._projected.clear()
        self._pending.clear()
        self._scratch = None
        with ExitStack() as cleanup:
            for animation in owned.values():
                cleanup.callback(animation.close)
