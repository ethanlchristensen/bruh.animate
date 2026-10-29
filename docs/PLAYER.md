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
explicit settings take precedence over a known preset. Unknown presets and
mismatched settings fail before a terminal opens. Use `effects.names()`,
`effects.snow.presets()` and `effects.snow.play(...)` for discovery and typed
preset/settings completion; see [the discovery guide](source/discovery.rst).

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
leaves the frame limit unset. `duration` limits wall-clock seconds after startup,
including paused or completed-held time. It is finite and non-negative, or `None`
for no duration limit. `duration=0` starts no effect, like `frames=0`; `play` still
opens/restores its Screen. The first stop condition wins. Sleeps are capped at
the deadline, but synchronous callbacks cannot be interrupted and may overrun.
Duration expiry performs the same owned-content cleanup as quitting.
Rates must be positive and finite, and dimensions non-empty.

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
Create new scenes to change membership. Layers can select independent tick rates.

## Layer regions, clocks, and temporary overlays

`Layer(animation, region=(x, y, width, height), updates_per_second=15)` clips
painting in scene coordinates and schedules fixed simulation ticks. The child
still receives a full-scene drawing buffer. There is no coordinate translation
or collision wall; negative origins and zero-sized regions are allowed.
Unconfigured layer rates keep forwarding every Scene update unchanged.

A fixed-rate layer waits for a full interval before its first tick. It draws
current state every presentation. `max_catch_up=5` bounds ticks per Scene update;
reaching it discards remaining accumulated time. Keep the parent update rate
high enough for your desired cadence, including in headless capture. Playback
already schedules its own solver steps, so leave its Layer rate unset for
responsive pause/step controls.

`TimedOverlay(animation, duration=2, delay=0)` owns a child for a visibility
window measured in supplied simulation seconds. Its child starts on activation,
closes on expiry, and paints nothing afterward. A zero duration or an entirely
skipped delayed window never starts the child. Cleanup remains idempotent after
partial failures, and drawing never advances time. The wrapper is single-use.
Pausing a sibling Playback does not pause the overlay.

Overlays participate in finite Scene completion. Use `on_complete="hold"` to
keep an endless background running after its only finite overlay expires.
See [the composition guide](source/composition.rst) and `beam_demo` for a complete
example combining a clipped panel, separate solver/background rates, a temporary
message, and a status display.

## Seeded headless rendering

Every built-in settings dataclass includes `seed: int | None`. Non-negative
seeds initialize independent Python/NumPy streams; `None` uses fresh entropy.
Named effects also accept a seed override through `play`, `Player`, `capture`,
`record`, and `effect_registry.create`. Configure instance/factory seeds at
construction. Overrides copy the selected configuration and preserve presets.

```python
from bruhanimate import Frame, effects

def inspect(frame: Frame) -> None:
    print(frame.time, frame.text())

effects.snow.capture(on_frame=inspect, seed=42, preset="light",
                     width=40, height=12, frames=4)
```

`capture` uses the Player loop with a virtual clock and immutable frame snapshots.
It requires `frames` or `duration`, uses positive FPS, generates no input/resize
events, and exits on completion by default. Duration is virtual seconds after
startup; rendering/callback cost does not affect it. The first frame is at zero
after one update, and no offline fixed ticks are dropped. Callbacks are synchronous;
retaining frames is optional. Ownership and failure cleanup match Player.
Headless rendering does not suppress an animation's devices or external inputs.

`effects.snow.record("snow.cast", seed=42, duration=5)` streams asciicast v2
changed-cell output. Existing paths require `overwrite=True`; borrowed text
streams stay open. The timeline ends at the last presented frame. No input,
environment, or audio is recorded. See [capture and recording](source/capture.rst)
for reproducibility conditions, cell restrictions, and the complete API.

## Movable panels

`Panel` gives any Animation a local surface, optional border/title, and movement:

```python
from bruhanimate import ImageEffect, Panel, play

panel = Panel(
    ImageEffect("Hello"), size=(20, 5), position=(2, 1),
    velocity=(8, 2), bounds=(0, 0, 40, 12), bounce=True, title="Message",
)
play(panel, frames=120, fps=60, updates_per_second=60)
```

Size is the content width/height; a border adds two columns and two rows.
Position and bounds use parent coordinates; children draw in local coordinates.
For built-in effects, pass a matching private buffer or use
`effect_factory=lambda local: SnowEffect(local, " ", SnowSettings())` so Panel
provides the correctly sized buffer at startup. Exactly one child source is required.

Panel owns its child, closes it once (including failed startup), and is single-use
after close. `updates_per_second` paces its child while motion uses the full
supplied dt. `finished` mirrors the child, and input handlers stay on Player.
Bounds clip both frame and content; bounce requires explicit bounds and pins
oversized axes at the bounds origin. Scene order controls stacking. `background=None`
allows unpainted child cells to reveal lower layers; child spaces still paint.
See the [Panel guide](source/panels.rst) for typed options, validation, and examples.

## Layout containers and text

`Row` and `Column` allocate `Slot` children using `Fixed(cells)` and
`Flex(weight=1)` sizes. `Spacer` reserves unpainted space. Containers support
integer gaps/uniform padding; build them through `play(effect_factory=layout.build)`.
Nest containers in slots, or use `Slot(effect_factory=...)` to receive a local
buffer for an effect or Panel. Layout trees are single-use and reflow in place.

```python
from bruhanimate import Column, Fixed, Label, Slot, StatusBar, play

layout = Column(
    Slot(Label("Dashboard", align="center"), size=Fixed(1)),
    Slot(Label(lambda: "Application state", vertical_align="middle")),
    Slot(StatusBar("Ready", right="q quit"), size=Fixed(1)),
    gap=1,
)
play(effect_factory=layout.build, frames=120, on_resize="resize")
```

Text callbacks refresh at startup and on update; drawing only reads cached text.
`TextStyle` provides foreground/background palette colors and bold. Label alignment
and overflow choices are Literal-typed for editor completion. Initially zero-area slots defer startup until visible; supplied children close on
cleanup even if never shown. Previously started hidden children keep updating and
participate in completion. Input remains on Player.
See [layouts and text widgets](source/layouts.rst) and run
`python -m bruhanimate.demos.dashboard_demo` for a complete example.

## Ownership, input, and failures

`ScrollView(animation, size=(width, height), content_size=(canvas_width, canvas_height))`
owns content on a larger canvas. Its `resize()` changes the viewport without
restarting content or consuming solver snapshots; `set_content_size()` explicitly
changes the canvas. `LogView(size=(width, height), max_lines=1000,
wrap="character", follow_tail=True)` retains bounded text history. Append during
input/update; draw only paints. Upward scrolling suspends following, and End
resumes it. Resize and history eviction preserve a logical line/character anchor
where possible. Both expose `bindings` for FocusTarget and typed scroll methods;
see [scrollable views](source/views.rst). Panel/layout own the views normally.

For declarative controls, import `KeyBinding`, `KeyBindings`, `FocusTarget`, and
`FocusGroup` from `bruhanimate`. Named keys such as `"space"` and `"shift+tab"`
use the `KeyName` Literal; `KeyBinding.character("n", action)` binds a character.
Actions return None, consume their key, and request exit only with `quit=True`.
Attach each target with `Panel(..., focus=target)` and pass
`event_handler=group.handle_event` to Player/play. The focused border highlights
selection; `StatusBar(center=group.help_text)` shows descriptions from bindings.

Routing is reserved navigation, focused bindings, then global bindings. FocusGroup
defaults to Tab/Shift+Tab and global fallback q/Q, Escape, Ctrl+C; supplying
`global_bindings` replaces the defaults. Unavailable targets are skipped, including
zero-area layout slots after resize. Standalone KeyBindings has no default quit
keys. `dispatch()` returns explicit `EventResult` values for custom routing;
use `handle_event`, not `dispatch`, for Player's Boolean handler contract.
See the [keyboard guide](source/keyboard.rst) for full options and examples.

Player registers effect cleanup before startup, covering partial acquisition,
update/draw errors, resize, quit, and Ctrl+C. It never closes a borrowed Screen.

Terminal write/flush errors also propagate after cleanup and invalidate the
presenter's diff baseline. Retrying a borrowed `FramePresenter` repaints the full
frame. On Unix, resuming a suspended process queues terminal-mode restoration and
a full repaint between frames; it does not restart content or count as a resize
when the dimensions are unchanged.
`manage_effect=False` borrows an already started instance and calls neither start
nor close. Named effects and factories always produce owned instances.

Default quit keys are q/Q, Escape, and Ctrl+C. `event_handler(event) -> bool` on
Player replaces default key routing; True requests exit. For a `TerminalEffect`,
pass `terminal.handle_event` so q reaches the shell while Escape exits. It keeps
bounded history/output processing and reaps owned processes and readers on close.

Resize raises `ScreenResizedError` after cleanup by default. Set
`on_resize="resize"` to refresh Screen dimensions, reflow existing content through
its optional `resize((width, height))` hook, and fully repaint. The typed
`ResizePolicy`, `Resizable`, and `ResizableAnimation` contracts are public.
Factories are not recalled; solver state, iterator ownership, pause/speed settings,
queued steps and accumulated layer time remain intact. Layouts call factories for
initially hidden slots only when they first become visible. Use `Panel(fit=True, ...)`
inside a slot to follow its changing allocation; fixed panels retain their geometry.
Snow, plasma, fire, rain and Matrix adapt their simulation areas without restarting.
Snow moves floor-connected piles to the bottom; fire anchors heat and its last flame
raster there too. Plasma redraws at its current phase. Rain retains drops and bolt
lifetimes and moves floor splashes; Matrix retains characters and per-row timing.
New Matrix cells initialize on the next update. Cropped state is discarded.
Explicit collision surfaces keep their coordinates and dimensions. Resize consumes
no randomness and advances no simulation ticks. All built-ins now have adapters:
grids retain cells, boids wrap their positions, Voronoi sites clamp to the new
bounds, and audio keeps its capture worker. Custom BaseEffect subclasses retain
the original clipping fallback. A temporarily empty
terminal suspends drawing/updates while quit polling and duration limits continue.
See the [resize guide](source/resize.rst) for custom content and backend contracts.
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

Layer masks/styling, Glitch/Focus/Dissolve/Wipe image transitions, public
AnimationSequence scheduling, and all built-in resize adapters are available.
See the [motion guide](source/motion.rst) for path/pulse/ripple accents and the
[export guide](source/exports.rst) for SVG, PNG, GIF, and MP4. Static collision
configuration on rain/snow/fire remains explicit; Scene does not infer physics
from painted layers.
