"""ASCII image transitions; masks and styling belong to generic Scene layers."""

from collections.abc import Sequence
from math import floor
from random import Random
from typing import Literal

from ._clock import _CycleClock
from ._validation import _seconds
from .bruhutil.bruhffer import Buffer
from .scene import ImageEffect

DissolveDirection = Literal["in", "out"]


class _ImageTransition(ImageEffect):
    """Implementation sharing, not an additional public content hierarchy."""

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None,
        y: float | None,
        duration: float,
        seed: int | None,
        repeat: bool,
        hold_duration: float,
        repeat_delay: float,
        reverse: bool,
    ) -> None:
        if seed is not None and type(seed) is not int:
            raise TypeError("seed must be an integer or None")
        for name, coordinate in (("x", x), ("y", y)):
            if coordinate is not None:
                if isinstance(coordinate, bool) or not isinstance(
                    coordinate, (int, float)
                ):
                    raise TypeError(f"{name} must be a number or None")
                _seconds(abs(coordinate), name)
        rows = tuple(image.splitlines() if isinstance(image, str) else image)
        if any(not isinstance(row, str) for row in rows):
            raise TypeError("image rows must be strings")
        super().__init__(rows, x=x, y=y, characters_per_second=1)
        self._clock = _CycleClock(
            duration, repeat, hold_duration, repeat_delay, reverse
        )
        self.seed, self.repeat = seed, repeat
        self.reverse = reverse
        self.hold_duration, self.repeat_delay = hold_duration, repeat_delay
        self._cells: tuple[tuple[int, int, str], ...] = ()

    @property
    def duration(self) -> float:
        """Transition time in seconds, excluding the optional hold and gap."""
        return self._clock.duration

    @property
    def finished(self) -> bool:
        """Empty images finish immediately; non-empty repeating images never do."""
        return not self._glyphs or (
            not self.repeat and self._clock.time >= self._clock.end_time
        )

    def update(self, dt: float) -> None:
        _seconds(dt, "dt")
        if self.finished:
            return
        self._clock.update(dt)
        self._cells = self._frame() if self._clock.visible else ()

    def _frame(self) -> tuple[tuple[int, int, str], ...]:
        raise NotImplementedError

    def draw(self, buffer: Buffer) -> None:
        x = (buffer.width() - self.width) // 2 if self.x is None else self.x
        y = (buffer.height() - len(self.rows)) // 2 if self.y is None else self.y
        for column, row, glyph in self._cells:
            buffer.put_char(floor(x) + column, floor(y) + row, glyph)


class GlitchImageEffect(_ImageTransition):
    """Fly glyphs from the image's left edge, flicker, then settle.

    Non-space glyphs launch in column order (top to bottom within a column), at
    characters_per_second. Each travels from one column before the image's left
    edge over travel_time seconds, jittering by at most one row and changing
    symbols at 20 Hz. Settled glyphs paint above flying ones. Spaces are transparent.

    x/y locate the final image; None centers each axis on the draw viewport.
    All timing uses update(dt) simulation seconds. Draw never advances state or
    randomness. Seeded glitches repeat independently of draw frequency. Resize
    recenters without restarting. duration is the time until the last arrival.
    finished becomes True after one entrance and the final image stays visible.
    repeat=True instead flies in, holds for hold_duration seconds, hides for
    repeat_delay seconds and repeats forever. Empty images finish immediately.

    reverse=True adds a backwards leg after the hold, retracing the same seeded
    frames over the same duration. With repeat=True the hidden gap follows that
    exit. Without repetition, finished waits for the return to the initial state.
    duration always describes one leg, excluding hold/gap.

    Supply plain single-cell text or text_to_image() rows. Rate and travel_time
    must be positive/finite; hold/gap must be non-negative/finite. Options are
    configured at construction. No children, external resources, or input are
    owned. start/close are safe to repeat without resetting progress. Use
    on_complete="hold" to keep a Scene background running after a single entrance.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        characters_per_second: float = 18,
        travel_time: float = 0.65,
        seed: int | None = None,
        repeat: bool = False,
        hold_duration: float = 3,
        repeat_delay: float = 1,
        reverse: bool = False,
    ) -> None:
        _seconds(characters_per_second, "characters_per_second")
        _seconds(travel_time, "travel_time")
        if characters_per_second == 0 or travel_time == 0:
            raise ValueError("characters_per_second and travel_time must be positive")
        rows = tuple(image.splitlines() if isinstance(image, str) else image)
        if any(not isinstance(row, str) for row in rows):
            raise TypeError("image rows must be strings")
        count = sum(char != " " for row in rows for char in row)
        super().__init__(
            rows,
            x=x,
            y=y,
            duration=count / characters_per_second + travel_time,
            seed=seed,
            repeat=repeat,
            hold_duration=hold_duration,
            repeat_delay=repeat_delay,
            reverse=reverse,
        )
        self.characters_per_second = characters_per_second
        self.travel_time, self._rate = travel_time, characters_per_second
        self._ordered = tuple(sorted(self._glyphs, key=lambda cell: (cell[0], cell[1])))
        random = Random(seed)
        self._phases = tuple(random.randrange(2**32) for _ in self._ordered)

    def _frame(self) -> tuple[tuple[int, int, str], ...]:
        flying, settled = [], []
        symbols = "#%&?/@+*=<>"
        for index, (column, row, glyph) in enumerate(self._ordered):
            age = self._clock.transition_time - (index + 1) / self._rate
            if age < 0:
                continue
            if age >= self.travel_time or self._clock.transition_time >= self.duration:
                settled.append((column, row, glyph))
                continue
            progress = age / self.travel_time
            tick = floor(age * 20)
            noise = (self._phases[index] + tick * 2654435761) & 0xFFFFFFFF
            jitter = noise % 3 - 1 if progress < 0.8 else 0
            flying.append(
                (
                    floor(-1 + (column + 1) * progress),
                    row + jitter,
                    symbols[(noise >> 8) % len(symbols)],
                )
            )
        return tuple(flying + settled)


class FocusImageEffect(_ImageTransition):
    """Assemble ASCII glyphs from seeded scattered positions into their image.

    scatter=(columns, rows) bounds random offsets from each glyph's final cell.
    Coordinates interpolate linearly over duration seconds. Colliding glyphs paint
    in original row order; the final image is exact. Scatter must be a pair of
    non-negative integers. It is relative to the image, not terminal dimensions,
    so resizing only recenters; clipped particles continue their trajectories.

    x/y default to centering. Spaces are transparent. Seed, timing, completion,
    repetition, lifecycle and plain single-cell input follow GlitchImageEffect:
    update advances simulation, draw is pure, repeat=True holds then hides before
    replaying the same scatter. duration is positive/finite; hold/gap are
    non-negative/finite seconds. The final image remains after a single entrance.
    No child ownership, input handling or external resources are involved.

    reverse=True retraces the same scatter after the hold. Repeating cycles then
    hide during the gap; a single round trip finishes at the scattered start state.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        duration: float = 2,
        scatter: tuple[int, int] = (12, 4),
        seed: int | None = None,
        repeat: bool = False,
        hold_duration: float = 3,
        repeat_delay: float = 1,
        reverse: bool = False,
    ) -> None:
        if (
            not isinstance(scatter, tuple)
            or len(scatter) != 2
            or any(type(value) is not int for value in scatter)
        ):
            raise TypeError("scatter must be a (columns, rows) integer tuple")
        if any(value < 0 for value in scatter):
            raise ValueError("scatter must be non-negative")
        super().__init__(
            image,
            x=x,
            y=y,
            duration=duration,
            seed=seed,
            repeat=repeat,
            hold_duration=hold_duration,
            repeat_delay=repeat_delay,
            reverse=reverse,
        )
        self.scatter = scatter
        random = Random(seed)
        self._offsets = tuple(
            (
                random.randint(-scatter[0], scatter[0]),
                random.randint(-scatter[1], scatter[1]),
            )
            for _ in self._glyphs
        )
        self._cells = self._frame()

    def _frame(self) -> tuple[tuple[int, int, str], ...]:
        remaining = 1 - self._clock.transition_time / self.duration
        return tuple(
            (column + round(dx * remaining), row + round(dy * remaining), glyph)
            for (column, row, glyph), (dx, dy) in zip(self._glyphs, self._offsets)
        )


class DissolveImageEffect(_ImageTransition):
    """Reveal or remove ASCII glyphs in a seeded random order.

    direction="in" begins blank and ends with the image; "out" begins with the
    image and ends blank. duration is positive, finite simulation seconds.
    Spaces are transparent; x/y default to centering on the draw viewport.
    Resize preserves progress and the random order. Seeded cycles replay the
    same order. repeat=True holds the final state for hold_duration seconds,
    paints nothing for repeat_delay seconds, then repeats. For an exit, the
    held final state is blank. Non-empty repeats never finish; one transition
    finishes at duration and retains its final state. Empty images finish at once.

    Plain single-cell input, lifecycle and timing follow GlitchImageEffect.
    Only update advances time; draw is pure. Configure options at construction.
    No child ownership, external resources or input routing are involved.

    reverse=True retraces the random order after the hold: an entrance dissolves
    out, while an exit dissolves back in. A single round trip finishes in its
    initial state; repeating cycles hide for repeat_delay before starting again.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        duration: float = 2,
        direction: DissolveDirection = "in",
        seed: int | None = None,
        repeat: bool = False,
        hold_duration: float = 3,
        repeat_delay: float = 1,
        reverse: bool = False,
    ) -> None:
        if direction not in ("in", "out"):
            raise ValueError("direction must be 'in' or 'out'")
        super().__init__(
            image,
            x=x,
            y=y,
            duration=duration,
            seed=seed,
            repeat=repeat,
            hold_duration=hold_duration,
            repeat_delay=repeat_delay,
            reverse=reverse,
        )
        self.direction = direction
        shuffled = list(self._glyphs)
        Random(seed).shuffle(shuffled)
        self._ordered = tuple(shuffled)
        self._cells = self._frame()

    def _frame(self) -> tuple[tuple[int, int, str], ...]:
        count = min(
            len(self._ordered),
            floor(
                self._clock.transition_time / self.duration * len(self._ordered) + 1e-9
            ),
        )
        return (
            self._ordered[:count] if self.direction == "in" else self._ordered[count:]
        )


WipeDirection = Literal["left", "right", "up", "down"]


class WipeImageEffect(_ImageTransition):
    """Reveal text with a straight edge moving in direction across its bounds.

    right reveals from the left, left from the right, down from the top, and up
    from the bottom. Spaces remain transparent. duration is positive simulation
    seconds for one leg. reverse retraces the wipe after hold_duration; repeat
    adds a blank repeat_delay before a new cycle. A non-repeating reverse ends
    blank; a normal one-shot retains the full image. Empty images finish at once.
    x/y=None centers on the current viewport, retaining progress across resize.
    Construction is inert; draw is pure. No resources, children or input are owned.
    """

    def __init__(
        self,
        image: str | Sequence[str],
        *,
        x: float | None = None,
        y: float | None = None,
        duration: float = 2,
        direction: WipeDirection = "right",
        repeat: bool = False,
        hold_duration: float = 3,
        repeat_delay: float = 1,
        reverse: bool = False,
    ) -> None:
        if direction not in ("left", "right", "up", "down"):
            raise ValueError("direction must be 'left', 'right', 'up', or 'down'")
        super().__init__(
            image,
            x=x,
            y=y,
            duration=duration,
            seed=None,
            repeat=repeat,
            hold_duration=hold_duration,
            repeat_delay=repeat_delay,
            reverse=reverse,
        )
        self.direction = direction
        self._cells = self._frame()

    def _frame(self) -> tuple[tuple[int, int, str], ...]:
        horizontal = self.direction in ("left", "right")
        extent = self.width if horizontal else len(self.rows)
        count = min(
            extent, floor(self._clock.transition_time / self.duration * extent + 1e-9)
        )
        backwards = self.direction in ("left", "up")
        return tuple(
            (x, y, glyph)
            for x, y, glyph in self._glyphs
            if (
                extent - 1 - (x if horizontal else y)
                if backwards
                else (x if horizontal else y)
            )
            < count
        )
