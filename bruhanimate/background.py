"""Cooperatively cancelled, bounded background solver playback."""

from collections.abc import Callable, Iterable
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Generic, cast

from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .playback import Playback, State


class BackgroundPlayback(Playback[State], Generic[State]):
    """Run a solver factory on one worker while Player remains responsive.

    factory(cancel_event) returns an iterable; it is called only after start, on
    the worker. The worker acquires/closes its iterator, copies snapshots before
    enqueueing when copy_state is supplied, and never touches rendering/input.
    Capacity bounds queued snapshots; at most one additional snapshot is in flight.
    Pausing stops consumption; the producer may fill the bounded queue. Empty
    queues retain the last frame, and queued manual steps wait for real states.
    Worker errors propagate on update after prior queued snapshots are consumed.

    The factory must check cancel_event and bound blocking I/O. Python threads
    cannot interrupt arbitrary next() calls. close signals cancellation and joins
    for close_timeout seconds; an unresponsive worker raises RuntimeError and can
    be joined by a later close. This is for responsive I/O/cooperative work, not
    a promise of CPU parallelism. Live workers are unsuitable for virtual-time
    capture/export; record deterministic snapshots first.
    """

    def __init__(
        self,
        factory: Callable[[Event], Iterable[State]],
        draw: Callable[[State, Buffer], None],
        *,
        capacity: int = 8,
        steps_per_second: float = 10,
        paused: bool = False,
        copy_state: Callable[[State], State] | None = None,
        max_catch_up: int = 5,
        close_timeout: float = 1,
    ) -> None:
        if not callable(factory):
            raise TypeError("factory must be callable")
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        _seconds(close_timeout, "close_timeout")
        super().__init__(
            (),
            draw,
            steps_per_second=steps_per_second,
            paused=paused,
            max_catch_up=max_catch_up,
        )
        self._factory, self._copy = factory, copy_state
        self._queue: Queue[tuple[str, object]] = Queue(capacity)
        self._cancel = Event()
        self._thread: Thread | None = None
        self._timeout = close_timeout
        self._cleanup_error: BaseException | None = None

    def _offer(self, kind: str, value: object) -> None:
        while not self._cancel.is_set():
            try:
                self._queue.put((kind, value), timeout=0.05)
                return
            except Full:
                pass

    def _produce(self) -> None:
        iterator = None
        error: BaseException | None = None
        try:
            iterator = iter(self._factory(self._cancel))
            while not self._cancel.is_set():
                try:
                    value = next(iterator)
                except StopIteration:
                    break
                self._offer("state", self._copy(value) if self._copy else value)
        except BaseException as exc:
            error = exc
        finally:
            try:
                close = getattr(iterator, "close", None)
                if close is not None:
                    close()
            except BaseException as exc:
                error = exc
                self._cleanup_error = exc
            self._offer("error" if error is not None else "done", error)

    def start(self) -> None:
        super().start()
        if self._thread is None:
            worker = Thread(
                target=self._produce, name="bruhanimate-solver", daemon=True
            )
            worker.start()
            self._thread = worker

    def _advance(self) -> None:
        if self.finished:
            return
        try:
            kind, value = self._queue.get_nowait()
        except Empty:
            return
        if kind == "error":
            if value is self._cleanup_error:
                self._cleanup_error = None
            raise cast(BaseException, value)
        if kind == "done":
            self._finished = True
            self._pending_steps = 0
            return
        self._state = cast(State, value)
        self._has_state = True
        self.steps += 1

    def update(self, dt: float) -> None:
        requested, before = self._pending_steps, self.steps
        super().update(dt)
        if requested and not self.finished:
            self._pending_steps = requested - (self.steps - before)

    def close(self) -> None:
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(self._timeout)
            if self._thread.is_alive():
                raise RuntimeError(
                    "Solver worker did not stop; factory must cooperate with cancellation"
                )
        super().close()
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                break
        error, self._cleanup_error = self._cleanup_error, None
        if error is not None:
            raise error
