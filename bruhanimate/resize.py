"""Optional viewport notifications, independent of animation ownership."""

from typing import Literal, Protocol, runtime_checkable

ResizePolicy = Literal["raise", "resize"]


def _size(size: tuple[int, int]) -> None:
    if (
        not isinstance(size, tuple)
        or len(size) != 2
        or any(type(n) is not int for n in size)
    ):
        raise TypeError("size must be a (width, height) tuple of integers")
    if any(n < 1 for n in size):
        raise ValueError("viewport dimensions must be positive")


@runtime_checkable
class Resizable(Protocol):
    """Optional capability for animations receiving a new parent viewport.

    Dimensions are positive (width, height) in cells. A notification must not
    advance simulation, consume input, or restart/close existing children.
    Owners call it between frames, before drawing at the new size. Animations
    without this method must already draw into arbitrary buffer dimensions.
    """

    def resize(self, size: tuple[int, int]) -> None:
        """Reflow the view while retaining live animation and solver state."""
        ...


def _resize(animation: object, size: tuple[int, int]) -> None:
    _size(size)
    if isinstance(animation, Resizable):
        animation.resize(size)
