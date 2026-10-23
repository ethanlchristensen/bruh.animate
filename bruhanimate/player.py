"""One playback loop for simulations, drawings, and composed scenes."""

from __future__ import annotations

import math
import operator
import time
from collections.abc import Callable
from contextlib import ExitStack
from typing import Literal, Protocol, runtime_checkable

from .bruheffect.registry import effect_registry
from .bruhutil.bruherrors import ScreenResizedError
from .bruhutil.bruhffer import Buffer
from .bruhutil.bruhscreen import Screen
from .bruhutil.bruhtypes import EffectType
from .resize import Resizable, ResizePolicy, _resize


@runtime_checkable
class Animation(Protocol):
    """Structural content contract; inheritance and registry membership are optional.

    Constructors are inert. Owners register cleanup before start and always close
    their content. An optional finished property (True/False/None) reports finite
    completion; an input handler is passed to Player explicitly.
    """

    def start(self) -> None:
        """Acquire playback resources; tolerate repeated calls."""
        ...

    def update(self, dt: float) -> None:
        """Advance simulation; dt is non-negative elapsed/fixed-tick seconds."""
        ...

    def draw(self, buffer: Buffer) -> None:
        """Paint current state without advancing it or retaining the target buffer."""
        ...

    def close(self) -> None:
        """Release owned resources, safely before start or after partial failure."""
        ...


class ResizableAnimation(Animation, Resizable, Protocol):
    """An Animation with a discoverable resize(width_height) viewport hook."""


class CallbackEffect:
    """Adapt drawing and optional simulation callbacks without a subclass.

    Resourceful content should implement Animation with explicit start/close.
    A bare callable is never guessed to be a drawing callback or a factory.
    """

    def __init__(
        self,
        draw: Callable[[Buffer], None],
        *,
        update: Callable[[float], None] | None = None,
    ):
        self._draw = draw
        self._update = update

    def start(self) -> None:
        pass

    def update(self, dt: float) -> None:
        if self._update is not None:
            self._update(dt)

    def draw(self, buffer: Buffer) -> None:
        self._draw(buffer)

    def close(self) -> None:
        pass


class FramePresenter:
    """Present changed cells in a batch and recycle the previous frame buffer.

    After present(), the supplied frame belongs to the presenter. Draw into the
    returned buffer instead; mutating the displayed frame would invalidate diffing.
    """

    def __init__(self, screen: Screen):
        self.screen = screen
        self.last_displayed = Buffer(screen.height, screen.width).clear_buffer(val=None)

    def resize(self) -> None:
        """Invalidate the previous frame after Screen.refresh_size()."""
        self.last_displayed = Buffer(
            self.screen.height, self.screen.width
        ).clear_buffer(val=None)

    def present(self, frame: Buffer) -> Buffer:
        self.screen.begin_frame()
        try:
            for y, x, value in self.last_displayed.get_buffer_changes(frame):
                self.screen.print_at(value, x, y, 1)
        finally:
            self.screen.flush_frame()
        previous = self.last_displayed
        self.last_displayed = frame
        return previous


EffectSource = EffectType | str | Animation
EffectFactory = Callable[[Buffer], Animation]


class Player:
    """Play an animation on a borrowed Screen.

    By default playback starts and closes the supplied effect, including on
    failure. manage_effect=False borrows an already started effect; factories
    always create owned effects. Player never closes the supplied Screen.

    Without updates_per_second, one update occurs per presentation. An explicit
    update rate uses fixed ticks independent of FPS, with bounded catch-up after
    stalls. frames counts presentations; duration limits elapsed wall-clock seconds
    after startup (including pauses/hold); None leaves each limit unset. A zero
    limit starts no content. Callbacks are synchronous and may overrun a deadline.
    fps=None disables pacing; uncapped updates use elapsed time when no fixed rate
    is supplied.
    Drawing receives a cleared buffer each presentation. BaseEffect retains its
    own simulation raster; draw() never advances it.

    on_complete='exit' stops after drawing an animation whose optional finished
    property is true. The default 'hold' keeps drawing and polling input. Content
    without this property (or reporting None) has no automatic completion.
    on_resize='raise' retains ScreenResizedError behavior. 'resize' refreshes the
    viewport and notifies optional Resizable content without restarting it.
    Snow, plasma, fire, rain and Matrix adapt their simulation area, retaining state.
    Other built-in rasters retain their original size and clip on shrink; extra
    cells on growth show the composition background. Factories are never recalled. Duration and frame limits continue across resize.
    Named effects accept seed to override their selected settings on a copy;
    None preserves the settings seed. Configure instance/factory seeds directly.
    """

    def __init__(
        self,
        screen: Screen,
        effect: EffectSource | None = None,
        *,
        effect_factory: EffectFactory | None = None,
        fps: float | None = 30,
        updates_per_second: float | None = None,
        frames: int | None = None,
        duration: float | None = None,
        on_complete: Literal["hold", "exit"] = "hold",
        on_resize: ResizePolicy = "raise",
        background: str = " ",
        settings: object | None = None,
        preset: str | None = None,
        seed: int | None = None,
        manage_effect: bool = True,
        event_handler: Callable[[int], bool] | None = None,
        presenter: FramePresenter | None = None,
        max_catch_up: int = 5,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if (effect is None) == (effect_factory is None):
            raise ValueError("Provide exactly one effect or effect_factory")
        if on_complete not in ("hold", "exit"):
            raise ValueError("on_complete must be 'hold' or 'exit'")
        for name, rate in (("fps", fps), ("updates_per_second", updates_per_second)):
            if rate is not None and (not math.isfinite(rate) or rate <= 0):
                raise ValueError(f"{name} must be a positive finite number or None")
        if frames is not None:
            frames = operator.index(frames)
            if frames < 0:
                raise ValueError("frames must be non-negative or None")
        _validate_duration(duration)
        max_catch_up = operator.index(max_catch_up)
        if max_catch_up < 1:
            raise ValueError("max_catch_up must be positive")
        if screen.height < 1 or screen.width < 1:
            raise ValueError("Player requires a non-empty screen")
        if (
            settings is not None or preset is not None or seed is not None
        ) and not isinstance(effect, str):
            raise ValueError("settings, preset and seed apply only to named effects")
        if not manage_effect and (
            effect_factory is not None or isinstance(effect, str)
        ):
            raise ValueError("Named effects and factories always create owned effects")
        self.screen = screen
        self.source = effect
        self.effect_factory = effect_factory
        self.fps = fps
        self.updates_per_second = updates_per_second
        self.frames = frames
        self.duration = duration
        if on_resize not in ("raise", "resize"):
            raise ValueError("on_resize must be 'raise' or 'resize'")
        self.on_resize = on_resize
        self.on_complete = on_complete
        self.background = background
        self.settings = settings
        self.preset = preset
        self.seed = seed
        self.manage_effect = manage_effect
        self.event_handler = event_handler
        self.presenter = presenter if presenter is not None else FramePresenter(screen)
        self.max_catch_up = max_catch_up
        self.clock = clock
        self.sleep = sleep
        self._running = False

    def _create_animation(self) -> Animation:
        source = self.source
        if self.effect_factory is not None:
            source = self.effect_factory(Buffer(self.screen.height, self.screen.width))
        elif isinstance(source, str):
            source = effect_registry.create(
                source,
                Buffer(self.screen.height, self.screen.width),
                self.background,
                settings=self.settings,
                preset=self.preset,
                seed=self.seed,
            )
        if isinstance(source, Animation):
            return source
        raise TypeError(
            "Expected an Animation; wrap drawing functions in CallbackEffect"
        )

    def _should_stop(self) -> bool:
        get_event = getattr(self.screen, "get_event", None)
        if get_event is None:
            return False
        # Bound polling so continuous input cannot starve rendering.
        for _ in range(100):
            event = get_event()
            if event is None:
                break
            if self.event_handler is not None:
                if self.event_handler(event):
                    return True
            elif event in (-1, 3, 27, ord("q"), ord("Q")):
                return True
        return False

    def run(self) -> int:
        """Run until quit, presentation limit, or configured finite completion.

        Returns:
            int: Frames presented, which may differ from simulation update count.

        Raises:
            ScreenResizedError: After closing owned content when size changes.
            Exception: Startup/update/draw/presentation errors after cleanup.
                KeyboardInterrupt instead ends normally. The borrowed Screen is
                never closed here; Screen.show/play owns terminal restoration.
        """
        if self._running:
            raise RuntimeError("This Player is already running")
        if self.frames == 0 or self.duration == 0:
            return 0
        self._running = True
        presented = 0
        try:
            with ExitStack() as cleanup:
                animation = self._create_animation()
                if self.manage_effect:
                    cleanup.callback(animation.close)
                    animation.start()
                back = Buffer(self.screen.height, self.screen.width)
                next_frame = next_tick = last_update = self.clock()
                deadline = (
                    last_update + self.duration if self.duration is not None else None
                )
                frame_interval = 1 / self.fps if self.fps is not None else 0.0
                tick_interval = (
                    1 / self.updates_per_second
                    if self.updates_per_second is not None
                    else frame_interval
                )
                while self.frames is None or presented < self.frames:
                    if self.screen.has_resized():
                        if self.on_resize == "raise":
                            raise ScreenResizedError("The screen was resized.")
                        if self.screen.refresh_size():
                            _resize(animation, (self.screen.width, self.screen.height))
                            self.presenter.resize()
                            back = Buffer(self.screen.height, self.screen.width)
                        else:
                            # A minimized/temporarily empty terminal must not spin,
                            # draw, or accumulate a burst of simulation catch-up.
                            if self._should_stop():
                                break
                            if deadline is not None and self.clock() >= deadline:
                                break
                            self.sleep(0.05)
                            next_frame = next_tick = last_update = self.clock()
                            continue
                    if self._should_stop():
                        break
                    now = self.clock()
                    if deadline is not None and now >= deadline:
                        break
                    if self.updates_per_second is None:
                        animation.update(
                            tick_interval
                            if frame_interval
                            else max(0.0, now - last_update)
                        )
                        last_update = now
                    else:
                        ticks = 0
                        while now + 1e-9 >= next_tick and ticks < self.max_catch_up:
                            if deadline is not None and self.clock() >= deadline:
                                break
                            animation.update(tick_interval)
                            next_tick += tick_interval
                            ticks += 1
                        if ticks == self.max_catch_up and now >= next_tick:
                            next_tick = now + tick_interval
                    back.clear_buffer(val=self.background)
                    animation.draw(back)
                    back = self.presenter.present(back)
                    presented += 1
                    if self.on_complete == "exit" and getattr(
                        animation, "finished", False
                    ):
                        break
                    if self.frames is not None and presented >= self.frames:
                        break
                    if frame_interval:
                        next_frame += frame_interval
                        wake_at = (
                            min(next_frame, deadline)
                            if deadline is not None
                            else next_frame
                        )
                        remaining = wake_at - self.clock()
                        if remaining > 0:
                            self.sleep(remaining)
                        else:
                            next_frame = self.clock()
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
        return presented


def play(
    effect: EffectSource | None = None,
    *,
    effect_factory: EffectFactory | None = None,
    fps: float | None = 30,
    updates_per_second: float | None = None,
    frames: int | None = None,
    duration: float | None = None,
    on_complete: Literal["hold", "exit"] = "hold",
    on_resize: ResizePolicy = "raise",
    background: str = " ",
    settings: object | None = None,
    preset: str | None = None,
    seed: int | None = None,
    event_handler: Callable[[int], bool] | None = None,
) -> int:
    """Open a screen, play owned content, and restore the terminal without a prompt.

    Discover names with effects.names() and configurations with
    effects.snow.presets(). Use effects.snow.play() for effect-specific preset
    and settings completion. Custom registered names remain accepted here.

    Supply an effect name, an Animation object, or effect_factory(buffer), with
    exactly one source. Named effects accept settings/preset; explicit settings
    take precedence. Factories receive a correctly sized private Buffer.
    seed overrides named-effect settings on an independent copy; None preserves
    their seed. Seeds are non-negative integers and do not change global RNGs.

    fps paces presentations (None is uncapped), updates_per_second optionally
    sets fixed simulation ticks, and frames limits presentations (None is endless).
    duration limits wall-clock seconds after startup, including paused/held time.
    None is unlimited; zero creates/starts no content. The first stop condition
    wins. A running callback cannot be interrupted, so a slow frame may overrun.
    on_complete selects hold/exit for content reporting a finished status.
    on_resize='resize' opts into live reflow; 'raise' is the compatibility default.
    Resizable content receives (width, height); other content must draw into any
    viewport. Factories are called once and solver state remains live.
    event_handler replaces the default quit bindings; returning True exits.
    Use Player directly for a borrowed Screen, injectable clock, or presenter.

    Returns:
        int: Number of presented frames. Rendering errors propagate after the
        terminal and owned content have been restored/closed.
    """

    _validate_duration(duration)
    if on_resize not in ("raise", "resize"):
        raise ValueError("on_resize must be 'raise' or 'resize'")
    if isinstance(effect, str):
        effect_registry.resolve_settings(
            effect, settings=settings, preset=preset, seed=seed
        )

    def run(screen):
        return Player(
            screen,
            effect,
            effect_factory=effect_factory,
            fps=fps,
            updates_per_second=updates_per_second,
            frames=frames,
            duration=duration,
            on_complete=on_complete,
            on_resize=on_resize,
            background=background,
            settings=settings,
            preset=preset,
            seed=seed,
            event_handler=event_handler,
        ).run()

    return Screen.show(run)


def _validate_duration(duration: float | None) -> None:
    if duration is None:
        return
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise TypeError("duration must be a number of seconds or None")
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("duration must be non-negative and finite or None")
