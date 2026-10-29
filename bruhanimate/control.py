"""Owned animation controls with explicit continuous or fixed-step timing."""

from typing import Literal

from ._clock import _fixed_steps
from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .keyboard import _set_visible
from .player import Animation
from .resize import _resize, _size

TimingMode = Literal["fixed", "continuous"]


class AnimationControl:
    """Own one child with pause/resume, queued single-step and time scaling.

    Choose mode explicitly. ``fixed`` accumulates scaled seconds and sends
    step_seconds per child update; use it for tick-based built-ins. ``continuous``
    forwards one scaled dt; use it only for children that integrate elapsed time.
    No child update occurs while paused, at zero scale, or on zero incoming dt,
    except an explicit paused step. Drawing continues without caching frames.

    Fixed scheduling uses Scene's catch-up policy: at most max_catch_up ticks per
    parent update, discarding the entire accumulator when that cap is reached.
    Otherwise fractional time survives pause, scale changes, resize and manual
    steps. Paused wall time is discarded. Controls never poll or forward input;
    route it through Player, independently of visibility and pause.

    Completion follows the child, and finished children receive no more updates.
    Ownership transfers at construction; never give the child to another owner.
    Close is idempotent before/after failed startup, and the wrapper is single-use.
    """

    def __init__(
        self,
        animation: Animation,
        *,
        mode: TimingMode,
        step_seconds: float = 1 / 30,
        time_scale: float = 1,
        paused: bool = False,
        max_catch_up: int = 5,
    ) -> None:
        if not isinstance(animation, Animation):
            raise TypeError("animation must implement Animation")
        if mode not in ("fixed", "continuous"):
            raise ValueError("mode must be fixed or continuous")
        _seconds(step_seconds, "step_seconds")
        if step_seconds == 0:
            raise ValueError("step_seconds must be positive")
        if type(paused) is not bool:
            raise TypeError("paused must be a bool")
        if type(max_catch_up) is not int or max_catch_up < 1:
            raise ValueError("max_catch_up must be a positive integer")
        self.time_scale = time_scale
        self._animation, self._mode = animation, mode
        self._step_seconds, self._max_catch_up = step_seconds, max_catch_up
        self._paused, self._pending_step = paused, False
        self._elapsed = 0.0
        self._started = self._closed = False

    @property
    def animation(self) -> Animation:
        return self._animation

    @property
    def mode(self) -> TimingMode:
        return self._mode

    @property
    def step_seconds(self) -> float:
        return self._step_seconds

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def time_scale(self) -> float:
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        _seconds(value, "time_scale")
        self._time_scale = value

    @property
    def finished(self) -> bool | None:
        return getattr(self.animation, "finished", None)

    def pause(self) -> None:
        """Stop automatic child updates; retain fractional fixed-step progress."""
        self._paused = True

    def resume(self) -> None:
        """Resume without replaying paused time; cancel any unconsumed manual step."""
        self._paused = False
        self._pending_step = False

    def toggle_pause(self) -> None:
        self.resume() if self.paused else self.pause()

    def step(self) -> None:
        """Request one step_seconds update on the next update call while paused.

        Requests coalesce until consumed, so key repeat cannot queue unbounded
        work. Stepping ignores time_scale, including zero, and works in either
        timing mode. A running or closed control rejects the request.
        """
        if self._closed or not self.paused:
            raise RuntimeError("step requires a paused, open control")
        self._pending_step = True

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("AnimationControl is closed")
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
            raise RuntimeError("AnimationControl must be started and not closed")
        if self.finished is True:
            self._pending_step = False
            return
        if self.paused:
            if self._pending_step:
                self._pending_step = False
                self.animation.update(self.step_seconds)
            return
        if dt == 0 or self.time_scale == 0:
            return
        scaled = dt * self.time_scale
        _seconds(scaled, "scaled dt")
        if scaled == 0:  # floating-point underflow must not tick a built-in
            return
        if self.mode == "continuous":
            self.animation.update(scaled)
        else:
            count, self._elapsed = _fixed_steps(
                self._elapsed, scaled, self.step_seconds, self._max_catch_up
            )
            for _ in range(count):
                if (
                    self._closed
                    or self.paused
                    or self.time_scale == 0
                    or self.finished is True
                ):
                    break
                self.animation.update(self.step_seconds)

    def resize(self, size: tuple[int, int]) -> None:
        _size(size)
        _resize(self.animation, size)

    def set_visible(self, visible: bool) -> None:
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        _set_visible(self.animation, visible)

    def draw(self, buffer: Buffer) -> None:
        if not self._started or self._closed:
            raise RuntimeError("AnimationControl must be started and not closed")
        self.animation.draw(buffer)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._pending_step = False
            self.animation.close()
