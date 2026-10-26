"""Callback-based interpolation driven by simulation time."""

from collections.abc import Callable
from math import isfinite
from typing import Literal

from ._clock import _CycleClock
from .bruhutil.bruhffer import Buffer

Easing = Literal["linear", "ease_in", "ease_out", "ease_in_out"]


class Tween:
    """Animate a scalar through a setter, without owning the setter's target.

    start applies the initial value; update applies interpolated values. draw is
    inert. Values and duration are finite; duration is positive seconds. Combine
    with a target animation in Scene (put Tween first to set values before the
    target updates). Use a setter to round integers or interpolate RGB/positions.
    reverse returns to the initial value; repeat loops without accumulating work
    across skipped cycles. A nonrepeating tween reports finished at its endpoint.
    close never closes the callback target. Construct a fresh Tween after close.
    """

    def __init__(
        self,
        setter: Callable[[float], None],
        start: float,
        end: float,
        *,
        duration: float = 1,
        easing: Easing = "linear",
        repeat: bool = False,
        reverse: bool = False,
    ) -> None:
        if not callable(setter):
            raise TypeError("setter must be callable")
        for value in (start, end):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError("Tween endpoints must be finite numbers")
        if easing not in ("linear", "ease_in", "ease_out", "ease_in_out"):
            raise ValueError("Unknown easing")
        self._setter, self._from, self._to = setter, start, end
        self.easing = easing
        self._clock = _CycleClock(duration, repeat, 0, 0, reverse)
        self._started = self._closed = False

    @property
    def finished(self) -> bool:
        return not self._clock.repeat and self._clock.time >= self._clock.end_time

    @property
    def value(self) -> float:
        t = self._clock.transition_time / self._clock.duration
        if self.easing == "ease_in":
            t *= t
        elif self.easing == "ease_out":
            t = 1 - (1 - t) ** 2
        elif self.easing == "ease_in_out":
            t = t * t * (3 - 2 * t)
        return self._from * (1 - t) + self._to * t

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("Tween is closed")
        if not self._started:
            self._started = True
            self._setter(self.value)

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Tween must be started before update")
        self._clock.update(dt)
        self._setter(self.value)

    def draw(self, buffer: Buffer) -> None:
        pass

    def close(self) -> None:
        self._closed = True
