"""Bounded application commands consumed explicitly at update boundaries."""

from collections import deque
from collections.abc import Callable


class ActionQueue[T]:
    """A bounded FIFO of application values, with no polling or lifecycle ownership.

    push returns False when full (drops the new value); existing commands retain
    order. Values are borrowed, not copied: prefer immutable payloads for replay.
    drain returns a detached tuple of up to limit commands for one update.
    Commands enqueued while processing that tuple wait for a later drain.
    Nothing executes during drawing, and the queue stores no unbounded history.
    Use only on the playback thread; this is not a worker-thread message queue.
    """

    def __init__(self, *, capacity: int = 64) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._items: deque[T] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._items)

    def push(self, action: T) -> bool:
        """Enqueue without executing; return whether the command was accepted."""
        if len(self._items) >= self.capacity:
            return False
        self._items.append(action)
        return True

    def bind(self, action: T) -> Callable[[], None]:
        """Return a KeyBinding-compatible enqueue callback, without enqueuing now.

        The callback discards the acceptance result; use push directly when the
        application needs to display overflow feedback. The payload is borrowed.
        """

        def enqueue() -> None:
            self.push(action)

        return enqueue

    def drain(self, *, limit: int = 1) -> tuple[T, ...]:
        """Remove a bounded snapshot for this update; zero leaves the queue untouched."""
        if type(limit) is not int or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        return tuple(self._items.popleft() for _ in range(min(limit, len(self._items))))

    def clear(self) -> None:
        """Discard pending commands without executing them."""
        self._items.clear()
