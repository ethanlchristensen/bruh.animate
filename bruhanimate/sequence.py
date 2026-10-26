"""Timed, factory-owned animation sequences, independent of presentation FPS."""

from collections.abc import Callable
from dataclasses import dataclass

from ._clock import _CycleClock
from ._validation import _seconds
from .bruhutil import Buffer
from .player import Animation
from .resize import _resize, _size


@dataclass(frozen=True)
class SequenceStep:
    """One animation factory and its simulation-second timing.

    factory must return a fresh, unowned Animation each time it is called.
    duration is positive; hold_duration freezes its final frame, then gap hides
    it. Early child completion also freezes its frame until the step expires.
    name labels the step for captions. Construction never calls the factory.
    """

    factory: Callable[[], Animation]
    duration: float
    hold_duration: float = 0
    gap: float = 0
    name: str = ""

    def __post_init__(self) -> None:
        if not callable(self.factory):
            raise TypeError("factory must be callable")
        if not isinstance(self.name, str):
            raise TypeError("name must be a string")
        for key in ("duration", "hold_duration", "gap"):
            _seconds(getattr(self, key), key)
        if self.duration == 0:
            raise ValueError("duration must be positive")
        _seconds(self.total_duration, "total step duration")

    @property
    def total_duration(self) -> float:
        """Seconds including the frozen hold and blank gap."""
        return self.duration + self.hold_duration + self.gap


class AnimationSequence:
    """Play timed steps, owning only the active child; optionally repeat forever.

    Factories run at start or entry into a step, never during construction/draw.
    Replaced children close before the next factory runs. close is idempotent,
    including before start and after failed startup. Do not reuse child instances.

    update(dt) uses non-negative simulation seconds. Large jumps skip unvisited
    steps/cycles without constructing them and update the destination child once
    with its elapsed time. This is scheduling, not a fixed-tick simulation replay.
    Child finished=True stops updates, but timing still follows SequenceStep.
    A finite sequence retains its last frame (or a blank final gap) when finished.
    Empty sequences finish immediately. Configuration is fixed at construction.

    Resize preserves the active child and forwards the latest viewport to future
    children before their first update/draw. No input is polled or automatically
    routed; pass a handler to Player explicitly if interactive content needs one.
    """

    def __init__(self, *steps: SequenceStep, repeat: bool = False) -> None:
        if any(not isinstance(step, SequenceStep) for step in steps):
            raise TypeError("steps must be SequenceStep instances")
        if type(repeat) is not bool:
            raise TypeError("repeat must be a bool")
        self.steps = tuple(steps)
        self.repeat = repeat
        self._lengths = tuple(step.total_duration for step in steps)
        self._duration = sum(self._lengths)
        _seconds(self._duration, "total sequence duration")
        self._clock = _CycleClock(self._duration or 1, repeat, 0, 0)
        self._index = 0
        self._offset = 0.0
        self._current: Animation | None = None
        self._size: tuple[int, int] | None = None
        self._started = self._closed = False

    @property
    def duration(self) -> float:
        """Seconds for one entire sequence, including holds and gaps."""
        return self._duration

    @property
    def index(self) -> int:
        """Zero-based active step; zero for an empty sequence."""
        return self._index

    @property
    def current(self) -> Animation | None:
        """Borrowed active child, or None before start/after close. Never close it."""
        return self._current

    @property
    def phase_name(self) -> str:
        """Active step name; empty for an empty sequence."""
        return self.steps[self.index].name if self.steps else ""

    @property
    def finished(self) -> bool:
        return not self.steps or (not self.repeat and self._clock.time >= self.duration)

    @property
    def visible(self) -> bool:
        if not self.steps or self._closed:
            return False
        step = self.steps[self.index]
        return step.gap == 0 or self._offset < step.duration + step.hold_duration

    def _release(self) -> None:
        child, self._current = self._current, None
        if child is not None:
            child.close()

    def _enter(self, index: int) -> None:
        try:
            self._release()
            self._index = index
            child = self.steps[index].factory()
            if not isinstance(child, Animation):
                raise TypeError("factory must return an Animation")
            self._current = child
            child.start()
            if self._size is not None:
                _resize(child, self._size)
        except BaseException:
            self.close()
            raise

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("AnimationSequence is closed")
        if not self._started:
            self._started = True
            if self.steps:
                self._enter(0)

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if not self._started or self._closed:
            raise RuntimeError("AnimationSequence must be started before update")
        if self.finished:
            return
        before = self._clock.time
        self._clock.update(dt)
        offset = self._clock.time
        index = 0
        while index < len(self.steps) - 1:
            tolerance = min(1e-9, self.steps[index].duration * 1e-6)
            if offset < self._lengths[index] - tolerance:
                break
            offset = max(0.0, offset - self._lengths[index])
            index += 1
        wrapped = self.repeat and (
            self._clock.time < before or dt >= self.duration - before
        )
        previous = self._offset
        if index != self.index or wrapped:
            self._enter(index)
            previous = 0
        step = self.steps[index]
        duration = step.duration
        for boundary in (duration, duration + step.hold_duration):
            if abs(offset - boundary) < min(1e-9, duration * 1e-6):
                offset = boundary
        self._offset = offset
        elapsed = max(0.0, min(offset, duration) - min(previous, duration))
        child = self._current
        if (
            child is not None
            and elapsed > 0
            and getattr(child, "finished", None) is not True
        ):
            child.update(elapsed)

    def draw(self, buffer: Buffer) -> None:
        if self._current is not None and self.visible:
            self._current.draw(buffer)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        self._size = size
        if self._current is not None:
            _resize(self._current, size)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._release()
