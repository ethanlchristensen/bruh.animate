"""Composition independent of terminal ownership, pacing, and presentation."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from math import floor

from .bruhutil.bruhffer import Buffer
from .player import Animation


@dataclass(frozen=True)
class Layer:
    """One animation in paint order. None cells always reveal lower layers.

    transparent=True also treats plain spaces as transparent. ANSI-colored
    spaces remain visible, so colored backgrounds can be composed deliberately.
    """

    animation: Animation
    transparent: bool = False


class Scene:
    """Own and paint animations from back to front through the shared Player.

    Each child gets an isolated drawing buffer. A scene owns each child once;
    close runs in reverse start order, including after partial startup failure.
    Build a new scene to change its membership during playback.
    """

    def __init__(self, *layers: Animation | Layer):
        self.layers = tuple(
            layer if isinstance(layer, Layer) else Layer(layer) for layer in layers
        )
        children = [layer.animation for layer in self.layers]
        if any(not isinstance(child, Animation) for child in children):
            raise TypeError("Scene children must implement Animation")
        if len({id(child) for child in children}) != len(children):
            raise ValueError("A Scene cannot own the same animation twice")
        self._cleanup: ExitStack | None = None
        self._scratch: Buffer | None = None

    @property
    def finished(self) -> bool | None:
        """Finish when all finite children finish, ignoring endless backgrounds.

        A finite child exposes a boolean finished property. A scene containing
        only endless content reports None. Nested scenes use the same rule.
        """
        statuses = [getattr(layer.animation, "finished", None) for layer in self.layers]
        finite = [status for status in statuses if status is not None]
        return all(finite) if finite else None

    def start(self) -> None:
        if self._cleanup is not None:
            return
        self._cleanup = ExitStack()
        try:
            for layer in self.layers:
                self._cleanup.callback(layer.animation.close)
                layer.animation.start()
        except BaseException:
            self.close()
            raise

    def update(self, dt: float) -> None:
        for layer in self.layers:
            layer.animation.update(dt)

    def draw(self, buffer: Buffer) -> None:
        size = (buffer.height(), buffer.width())
        if (
            self._scratch is None
            or (self._scratch.height(), self._scratch.width()) != size
        ):
            self._scratch = Buffer(*size)
        for layer in self.layers:
            self._scratch.clear_buffer(val=None)
            layer.animation.draw(self._scratch)
            for y, row in enumerate(self._scratch.buffer):
                for x, cell in enumerate(row):
                    if cell is not None:
                        value = str(cell)
                        if not (layer.transparent and value == " "):
                            buffer.put_char(x, y, value)

    def close(self) -> None:
        cleanup, self._cleanup = self._cleanup, None
        if cleanup is not None:
            cleanup.close()


class ImageEffect:
    """Draw text or ASCII image rows, centered unless x/y are supplied.

    velocity is (columns/second, rows/second). Movement happens in update(),
    and out-of-bounds content is clipped. Spaces paint; use Layer transparency
    to reveal an animated background through them.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        velocity: tuple[float, float] = (0, 0),
    ):
        self.rows = tuple(image.splitlines() if isinstance(image, str) else image)
        self.width = max(map(len, self.rows), default=0)
        self.x, self.y = x, y
        self.velocity = velocity
        self._offset_x = self._offset_y = 0.0

    def start(self) -> None:
        pass

    def update(self, dt: float) -> None:
        self._offset_x += self.velocity[0] * dt
        self._offset_y += self.velocity[1] * dt

    def draw(self, buffer: Buffer) -> None:
        x = (buffer.width() - self.width) // 2 if self.x is None else self.x
        y = (buffer.height() - len(self.rows)) // 2 if self.y is None else self.y
        for row, text in enumerate(self.rows):
            buffer.put_at(
                floor(x + self._offset_x), floor(y + self._offset_y) + row, text
            )

    def close(self) -> None:
        pass
