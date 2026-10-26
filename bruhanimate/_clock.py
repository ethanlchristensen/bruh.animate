"""Shared bounded simulation clocks."""

from ._validation import _seconds


class _CycleClock:
    """Shared simulation clock, with bounded work across arbitrarily many cycles."""

    def __init__(
        self,
        duration: float,
        repeat: bool,
        hold: float,
        gap: float,
        reverse: bool = False,
    ):
        _seconds(duration, "duration")
        if duration == 0:
            raise ValueError("duration must be positive")
        if type(repeat) is not bool:
            raise TypeError("repeat must be a bool")
        if type(reverse) is not bool:
            raise TypeError("reverse must be a bool")
        _seconds(hold, "hold_duration")
        _seconds(gap, "repeat_delay")
        self.duration, self.repeat, self.hold = duration, repeat, hold
        self.reverse = reverse
        self.end_time = duration + hold + duration if reverse else duration
        _seconds(self.end_time, "total transition duration")
        self.period = self.end_time + gap if reverse else duration + hold + gap
        _seconds(self.period, "total cycle duration")
        self.time = 0.0

    @property
    def visible(self) -> bool:
        end = self.end_time if self.reverse else self.duration + self.hold
        return not self.repeat or self.time < end

    @property
    def transition_time(self) -> float:
        """Time sampled by the effect: forwards, held, then optionally backwards."""
        if self.reverse and self.time > self.duration + self.hold:
            return max(0.0, self.end_time - self.time)
        return min(self.duration, self.time)

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if self.repeat:
            remainder = dt % self.period
            # Subtraction avoids overflow even for very large finite durations.
            remaining = self.period - self.time
            self.time = (
                remainder - remaining
                if remainder >= remaining
                else self.time + remainder
            )
            tolerance = min(1e-9, self.duration * 1e-6)
            for boundary in (
                self.duration,
                self.duration + self.hold,
                self.end_time,
                self.period,
            ):
                if abs(self.time - boundary) < tolerance:
                    self.time = boundary % self.period
        else:
            self.time = min(self.end_time, self.time + dt)
            if self.end_time - self.time < min(1e-9, self.duration * 1e-6):
                self.time = self.end_time
