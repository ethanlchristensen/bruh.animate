"""Explicit drawing cache for content whose changes are application-controlled."""

from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .keyboard import _set_visible
from .player import Animation
from .resize import _resize, _size


class CachedAnimation:
    """Own a child and reuse its drawing until invalidate or resize is called.

    Updates still run every tick. The application must invalidate after changing
    visible state; this is intended for static/rarely changing content. It does
    not cache arbitrary animation automatically. None cells remain transparent.
    Dimensions are learned from draw, or resize; snapshots never share cells with
    a presented Buffer. Completion and visibility follow the child; route input
    explicitly. Close is idempotent, including before/after failed startup.
    """

    def __init__(self, animation: Animation) -> None:
        if not isinstance(animation, Animation):
            raise TypeError("animation must implement Animation")
        self.animation = animation
        self._frame: Buffer | None = None
        self._dirty = True
        self._started = self._closed = False

    @property
    def finished(self) -> bool | None:
        return getattr(self.animation, "finished", None)

    def invalidate(self) -> None:
        self._dirty = True

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("CachedAnimation is closed")
        if not self._started:
            self._started = True
            try:
                self.animation.start()
            except BaseException:
                self.close()
                raise

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started or self._closed:
            raise RuntimeError("CachedAnimation must be started before update")
        self.animation.update(dt)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self.invalidate()
        _resize(self.animation, size)

    def set_visible(self, visible: bool) -> None:
        _set_visible(self.animation, visible)

    def draw(self, buffer: Buffer) -> None:
        if not self._started or self._closed:
            raise RuntimeError("CachedAnimation must be started before draw")
        if self._frame is None or (self._frame.width(), self._frame.height()) != (
            buffer.width(),
            buffer.height(),
        ):
            self._frame = Buffer(buffer.height(), buffer.width())
            self._dirty = True
        if self._dirty:
            self._frame.clear_buffer(val=None)
            self.animation.draw(self._frame)
            # Freeze arbitrary cell objects at the cache boundary.
            self._frame.buffer = [
                [None if c is None else str(c) for c in row]
                for row in self._frame.buffer
            ]
            self._dirty = False
        buffer.sync_over_top(self._frame)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._frame = None
            self.animation.close()
