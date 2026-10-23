# Player and composition

Implemented for 1.0.0. There is one playback loop and no legacy effect adapters
or renderer subclasses. The registry discovers and constructs effects; Player
runs them. These responsibilities remain separate.

## Three entry points

```python
from bruhanimate import play
play("snow", preset="light", fps=60, updates_per_second=30)
```

Use `effect_factory=build` when the animation needs an allocated screen-sized
`Buffer`. `build(buffer)` returns an animation. Pass either an effect name/object
or a factory, never both. `settings` and `preset` apply only to named effects;
explicit settings take precedence over a preset.

`Player(screen, animation, ...)` borrows an existing Screen. `play(...)` opens and
restores its own Screen with `Screen.show`. Neither pauses for an end prompt.
Both return the number of presented frames. Use `Player` for a fake clock, custom presenter, or borrowed effect lifecycle.
Both `play` and `Player` accept an explicit event_handler.

## Animation contract

An object implements `Animation` when it provides these methods:

| Method | Responsibility |
| --- | --- |
| `start()` | Acquire devices, threads, or other playback resources. Be idempotent. |
| `update(dt)` | Advance simulation; dt is seconds. |
| `draw(buffer)` | Paint current state; never advance simulation or consume solver input. |
| `close()` | Release resources; safe before start, after failed start, and repeatedly. |

Constructors configure objects without opening terminals, devices, or processes.
`BaseEffect` is an abstract helper for simulations with persistent private buffers.
Subclasses must implement `update(dt)`. Its default `draw` copies visible cells as
immutable strings, preserving `None` transparency and isolating mutable color
objects from previously displayed frames. A subclass may override draw.

```python
from bruhanimate import BaseEffect, play

class Cursor(BaseEffect):
    def __init__(self, buffer):
        super().__init__(buffer, " ")
        self.position = 0.0

    def update(self, dt):
        self.position += dt * 5  # columns per second
        self.buffer.clear_buffer()
        self.buffer.put_char(int(self.position) % self.buffer.width(), 0, "*")

play(effect_factory=Cursor, fps=60, updates_per_second=30)
```

`CallbackEffect(draw, update=...)` implements the same interface for small
scripts without a subclass. Resource-owning custom content should implement
Animation explicitly so it can expose startup and cleanup.

## Timing

`fps=30` paces presentations. `fps=None` removes presentation pacing.
`updates_per_second=10` schedules fixed ticks independently of presentation FPS.
An initial tick runs before the first draw. A slow frame can trigger catch-up
updates; `max_catch_up=5` bounds them, discarding excess wall time after a stall.
There is no interpolation between simulation states.

With `updates_per_second=None` (the default), each presentation gets one update.
A paced player passes `1 / fps`; an uncapped player passes elapsed time (initially
zero). Built-in simulations are discrete and advance once per update, including
when dt is zero. Set an explicit update rate to keep their speed independent of
FPS. Their probabilities, halt intervals, and existing speed settings use ticks;
this release does not convert all simulation equations to seconds.

`frames` counts presentations, not updates. `frames=0` creates no effect and
opens no effect resources; `play` still opens/restores a screen. `frames=None`
runs until quit. Rates must be positive and finite, and dimensions non-empty.

## Composition

```python
from bruhanimate import Buffer, ImageEffect, Layer, Scene, effect_registry, play

def build(buffer):
    fireworks = effect_registry.create("firework", buffer, " ")
    stars = effect_registry.create(
        "stars", Buffer(buffer.height(), buffer.width()), " ", preset="color"
    )
    return Scene(stars, Layer(fireworks, transparent=True), ImageEffect("Finished!"))

play(effect_factory=build, fps=60, updates_per_second=30)
```

Each child draws into an isolated scratch buffer; layers paint back to front.
`None` is always transparent. Spaces paint unless a `Layer` opts into plain-space
transparency. ANSI-colored spaces still paint. Each presentation recomposes from
current state, so disappearing overlays reveal lower layers without erase logic.

`ImageEffect(text_or_rows, x=None, y=None, velocity=(0, 0))` centers by default.
Explicit coordinates can be zero or negative, and content clips to the buffer.
Velocity is columns/second and rows/second; movement occurs only in update.
Text must use single-cell glyphs. ANSI styling belongs in individual buffer cells;
raw escape sequences in image rows are not parsed into styled glyphs.

Scene owns its children, starts once, and closes started children in reverse
order. A child whose start fails is also closed. Cleanup continues if another
child's close raises. Duplicate direct ownership is rejected. Do not share one
animation instance between scenes or players; immutable model data can be shared.
Create new scenes to change membership. All children currently use one tick rate.

## Ownership, input, and failures

Player registers effect cleanup before startup, covering partial acquisition,
update/draw errors, resize, quit, and Ctrl+C. It never closes a borrowed Screen.
`manage_effect=False` borrows an already started instance and calls neither start
nor close. Named effects and factories always produce owned instances.

Default quit keys are q/Q, Escape, and Ctrl+C. `event_handler(event) -> bool` on
Player replaces default key routing; True requests exit. For a `TerminalEffect`,
pass `terminal.handle_event` so q reaches the shell while Escape exits. It keeps
bounded history/output processing and reaps owned processes and readers on close.

Resize raises `ScreenResizedError` after cleanup; there is no automatic reflow.
Other failures propagate after cleanup. KeyboardInterrupt ends playback normally.
Audio construction is inert; start opens capture, and close joins its worker.
Audio backend errors remain visible through the effect's existing error display.

`FramePresenter` batches changed-cell output and rotates buffers. After
`present(frame)`, the presenter owns that frame; draw into the returned buffer.
Never mutate a previously presented buffer, and do not write directly to Screen
while Player owns presentation.

## Solver playback and completion

Playback consumes a lazy snapshot iterator and pairs it with draw(state, buffer).
It provides pause/resume, queued single steps, and speed controls; GridViewport
handles board-to-screen conversion, spacing, centering, camera offsets, and clipping.
See [the solver playback guide](SOLVER_PLAYBACK.md) and the grid_demo example.

Pass event_handler=playback.handle_event to enable solver controls through play or
Player. Pausing Playback leaves unrelated background effects running.
on_complete="hold" is the default; "exit" stops after presenting completed content.
An optional finished property signals completion. None/missing means endless;
Scene completes when all finite children finish, ignoring endless backgrounds.

## Next steps

Duration limits, masks, independent general layer clocks, character-assembly motion,
recording/export, and resize reconstruction remain future work. Static collision
configuration on rain/snow/fire remains explicit; Scene does not infer physics
from painted layers. See [the roadmap](ROADMAP.md).
