"""Opt-in bounded history for lazy solver playback."""

from collections import deque
from collections.abc import Callable, Iterable
from typing import Generic, cast

from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen
from .playback import Playback, State


class HistoryPlayback(Playback[State], Generic[State]):
    """Playback with a bounded recent-snapshot window and named bookmarks.

    The ordinary Playback still retains one snapshot. Here capacity counts
    snapshots (not bytes); evicted states and their bookmarks cannot be revisited.
    States must be immutable, or pass copy_state. position/seek use zero-based
    source indexes; steps still counts total snapshots consumed. back/seek pause
    and queue a move for update, never consume the source or mutate during draw.
    Forward playback reuses retained snapshots before requesting new ones. Left
    arrow/b go backward; existing pause/step/speed/quit bindings remain available.
    """

    def __init__(
        self,
        states: Iterable[State],
        draw: Callable[[State, Buffer], None],
        *,
        capacity: int = 100,
        steps_per_second: float = 10,
        paused: bool = False,
        copy_state: Callable[[State], State] | None = None,
        max_catch_up: int = 5,
    ) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        super().__init__(
            states,
            draw,
            steps_per_second=steps_per_second,
            paused=paused,
            copy_state=copy_state,
            max_catch_up=max_catch_up,
        )
        self._history: deque[State] = deque(maxlen=capacity)
        self._position = -1
        self._source_finished = False
        self._seek: int | None = None
        self._bookmarks: dict[str, int] = {}

    @property
    def position(self) -> int:
        return self._position

    @property
    def history_start(self) -> int:
        return self.steps - len(self._history)

    @property
    def bookmarks(self) -> dict[str, int]:
        return dict(self._bookmarks)

    def bookmark(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("bookmark name must be nonempty")
        if not self.has_state:
            raise RuntimeError("No snapshot to bookmark")
        self._bookmarks[name] = self.position

    def seek(self, index: int) -> None:
        if type(index) is not int or not self.history_start <= index < self.steps:
            raise ValueError("Snapshot is outside retained history")
        self.pause()
        self._pending_steps = 0
        self._seek = index

    def back(self) -> None:
        position = self._seek if self._seek is not None else self.position
        if position > self.history_start:
            self.seek(position - 1)

    def handle_event(self, event: int) -> bool:
        if event in (Screen.KEY_LEFT, ord("b"), ord("B")):
            self.back()
            return False
        return super().handle_event(event)

    def _advance(self) -> None:
        if self.position < self.steps - 1:
            self._position += 1
            self._state = self._history[self.position - self.history_start]
            self._finished = self._source_finished and self.position == self.steps - 1
            return
        if self._source_finished:
            self._finished = True
            return
        before = self.steps
        super()._advance()
        if self.finished:
            self._source_finished = True
        elif self.steps > before:
            # _advance has already applied copy_state, including yielded None.
            self._history.append(cast(State, self.state))
            self._position = self.steps - 1
            self._bookmarks = {
                name: index
                for name, index in self._bookmarks.items()
                if index >= self.history_start
            }

    def update(self, dt: float) -> None:
        # Validate lifecycle/time before applying a queued seek, even at EOF.
        if self._seek is not None:
            from ._validation import _seconds

            _seconds(dt, "dt")
            if not self._started or self._closed:
                raise RuntimeError(
                    "Playback must be started and not closed before update"
                )
            self._position, self._seek = self._seek, None
            self._state = self._history[self.position - self.history_start]
            self._finished = self._source_finished and self.position == self.steps - 1
        super().update(dt)
