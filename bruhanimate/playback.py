"""Lazy, bounded playback of solver snapshots through the Animation interface."""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, Iterable, Iterator
from typing import Generic, TypeVar, cast

from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen

State = TypeVar("State")


class Playback(Generic[State]):
    """Keep one current snapshot from a lazy state source.

    draw(state, buffer) reads the current snapshot without consuming input.
    Sources should yield independent/immutable states; pass copy_state=deepcopy
    when the producer reuses mutable data. No history or lookahead is retained.

    This is a single-use animation and owns the iterator acquired at start().
    Its optional close() runs on exhaustion or playback cleanup. next() executes
    synchronously: expensive solvers should yield bounded units of work.
    """

    def __init__(
        self,
        states: Iterable[State],
        draw: Callable[[State, Buffer], None],
        *,
        steps_per_second: float = 10,
        paused: bool = False,
        copy_state: Callable[[State], State] | None = None,
        max_catch_up: int = 5,
    ):
        max_catch_up = operator.index(max_catch_up)
        if max_catch_up < 1:
            raise ValueError("max_catch_up must be positive")
        self._states: Iterable[State] | None = states
        self._draw = draw
        self._copy_state = copy_state
        self.max_catch_up = max_catch_up
        self._steps_per_second = self._validate_rate(steps_per_second)
        self._paused = bool(paused)
        self._iterator: Iterator[State] | None = None
        self._started = False
        self._closed = False
        self._finished = False
        self._has_state = False
        self._state: State | None = None
        self._elapsed = 0.0
        self._discard_dt = False
        self._pending_steps = 0
        self.steps = 0

    @staticmethod
    def _validate_rate(rate: float) -> float:
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("steps_per_second must be positive and finite")
        return rate

    @property
    def steps_per_second(self) -> float:
        return self._steps_per_second

    @steps_per_second.setter
    def steps_per_second(self, rate: float) -> None:
        self._steps_per_second = self._validate_rate(rate)
        self._elapsed = 0.0
        self._discard_dt = True

    @property
    def state(self) -> State | None:
        """Current snapshot; use has_state to distinguish a yielded None."""
        return self._state

    @property
    def has_state(self) -> bool:
        return self._has_state

    @property
    def finished(self) -> bool:
        """True only after source exhaustion, not after early close/quit."""
        return self._finished

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """Suspend automatic consumption, discarding accumulated solver time."""
        self._paused = True
        self._elapsed = 0.0

    def resume(self) -> None:
        """Resume without paused-time catch-up or leftover queued manual steps."""
        if self._paused:
            self._paused = False
            self._elapsed = 0.0
            self._discard_dt = True
            self._pending_steps = 0

    def step(self) -> None:
        """Pause and request one source advance on the next update."""
        self.pause()
        if not self.finished:
            self._pending_steps += 1

    def handle_event(self, event: int) -> bool:
        """Player event handler: space/p pause, n/right step, +/- speed, q quit."""
        if event in (-1, 3, 27, ord("q"), ord("Q")):
            return True
        if event in (ord(" "), ord("p"), ord("P")):
            self.resume() if self.paused else self.pause()
        elif event in (ord("n"), ord("N"), ord("."), Screen.KEY_RIGHT):
            self.step()
        elif event in (ord("+"), ord("=")):
            self.steps_per_second = min(240, self.steps_per_second * 2)
        elif event in (ord("-"), ord("_")):
            self.steps_per_second = max(0.25, self.steps_per_second / 2)
        return False

    def start(self) -> None:
        """Acquire an iterator without calling next; closed Playback cannot restart."""
        if self._closed:
            raise RuntimeError("Playback is single-use; construct a new instance")
        if not self._started:
            if self._states is None:
                raise TypeError("states must be iterable")
            self._iterator = iter(self._states)
            self._states = None
            self._started = True

    def _close_source(self) -> None:
        iterator, self._iterator = self._iterator, None
        close = getattr(iterator, "close", None)
        if close is not None:
            close()

    def _advance(self) -> None:
        if self.finished:
            return
        assert self._iterator is not None
        try:
            state = next(self._iterator)
        except StopIteration:
            self._finished = True
            self._pending_steps = 0
            self._close_source()
            return
        self._state = self._copy_state(state) if self._copy_state else state
        self._has_state = True
        self.steps += 1

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Playback must be started and not closed before update")
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be non-negative and finite")
        if self.finished:
            return
        if self._pending_steps:
            count = min(self._pending_steps, self.max_catch_up)
            self._pending_steps -= count
            for _ in range(count):
                self._advance()
            return
        if self.paused:
            return
        if self._discard_dt:
            dt = 0.0
            self._discard_dt = False
        if not self.has_state:
            self._advance()
            return
        self._elapsed += dt
        interval = 1 / self.steps_per_second
        count = 0
        tolerance = min(1e-9, interval * 1e-6)
        while self._elapsed + tolerance >= interval and count < self.max_catch_up:
            self._elapsed = max(0.0, self._elapsed - interval)
            self._advance()
            count += 1
            if self.finished:
                break
        if count == self.max_catch_up:
            self._elapsed = 0.0

    def draw(self, buffer: Buffer) -> None:
        """Read the current snapshot; draw nothing before the first state."""
        if self.has_state:
            self._draw(cast(State, self._state), buffer)

    def close(self) -> None:
        """Close the acquired iterator once, retaining the final snapshot for inspection."""
        if not self._closed:
            self._closed = True
            self._states = None
            self._close_source()
