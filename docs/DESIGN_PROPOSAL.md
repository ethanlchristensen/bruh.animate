# Effect and playback design

Status: implemented foundation for the 1.0.0 major release, October 22, 2026.
The user's major-release decision replaces the earlier compatibility proposal:
built-in effects and demos migrate directly, with no legacy adapters or wrappers.
See [the player guide](PLAYER.md) and [migration guide](MIGRATING_1.0.md).

## Responsibilities

| Component | Owns |
| --- | --- |
| Animation protocol | start, update(dt), draw(buffer), close |
| BaseEffect | Persistent simulation raster and abstract update method |
| CallbackEffect | Explicit drawing and optional update callbacks |
| Scene / Layer | Paint order, isolated child draws, transparency, child lifecycle |
| ImageEffect | Text/image placement and elapsed-time panning |
| Playback | Lazy solver snapshots, independent step clock, solver controls, source cleanup |
| GridViewport / draw_grid | Grid layout, camera, clipping, cell styling, paths/markers |
| TerminalEffect | Shell input, output history, owned processes/readers |
| Player | Clock, input polling, startup/cleanup, update and draw scheduling |
| FramePresenter | Changed-cell batching and buffer rotation |
| Screen | Platform terminal state, normalized input, output |
| EffectRegistry | Names, classes, settings, presets, construction |

The registry constructs stateful objects. Turning every effect into a registered
rendering function would hide simulation state, resource ownership, and cleanup.
Callbacks remain useful for small custom drawings without requiring registration.
There is one Player loop; content types do not subclass it to get different layouts.

## Contracts and tradeoffs

Drawing reads current state without advancing it. BaseEffect simulations retain
their raster; draw copies cells to stable strings so mutable color objects cannot
modify the previous presentation. Callback and image content draw into cleared
presentation buffers. Scene recomposes isolated children back to front, with None
transparency and explicit opt-in plain-space transparency.

An explicit update rate separates logical ticks from display FPS. Most built-ins
remain discrete simulations with tick-based probabilities and speed settings;
a dt parameter alone does not turn their equations into elapsed-time physics.
Catch-up is bounded to keep input and presentation responsive after stalls.
Image motion and custom effects can use seconds directly.

Construction opens no devices, terminals, threads, or processes. Owners register
cleanup before startup, and Scene closes children in reverse order even if one
cleanup fails. Player borrows Screen; play owns it through Screen.show. The same
animation instance must not have multiple lifecycle owners.

Terminal input routing is explicit because q is legitimate shell input. Player's
custom handler replaces its default quit policy. Resize stops playback cleanly;
automatic reconstruction awaits a state-preservation policy.

## Verified behavior

Tests cover simulation/presentation separation, layer transparency, centering,
panning/clipping, stable mutable-cell snapshots, changed-cell suppression,
partial startup failure, reverse cleanup, audio worker ownership, screen rollback,
and real subprocess/Windows descendant cleanup. Every registry preset and every
demo runs at representative normal and tiny positive dimensions. Physical audio
and native Unix terminals require separate checks.

## Remaining design work

Playback now consumes lazy iterators only on logical updates, retains one
snapshot, and closes its owned iterator. Solver pause/step/rate controls work
independently of background effects. GridViewport supplies centered/clipped board
coordinates; Scene propagates finite-child completion without special-casing
Playback. play exposes explicit input routing and hold/exit completion policies.

Duration, masks, independent general layer clocks, character assembly,
recording/export, and resize reconstruction remain open. Collision masks are explicit effect inputs; Scene does not infer physics
from visible glyphs. Promote puzzle helpers only after two examples show a useful
shared contract; puzzle-specific branching stays in application code.

## Research informing the direction

These primary references informed the earlier design research; they are design
comparisons rather than dependencies or promises of matching behavior.

| Reference | Relevant approach | Design implication |
| --- | --- | --- |
| [Asciimatics: scenes and effects](https://asciimatics.readthedocs.io/en/stable/animation.html) | Scenes contain ordered effects and are played by a shared entry point. Paths represent movement. | Composition and motion can be independent of playback. |
| [Asciimatics: rendering](https://asciimatics.readthedocs.io/en/stable/rendering.html) | Its renderer objects generate text and color maps; effects place/use that content. | Its term "renderer" describes a different responsibility from bruhanimate's classes. Compare responsibilities, not names. |
| [Rich: Live display](https://rich.readthedocs.io/en/stable/live.html) | A live display presents different renderables, supports automatic or manual refresh, and has a context-managed lifetime. | Terminal presentation and cleanup can be shared across content types. Rich is not being proposed as a replacement animation engine. |
| [Matplotlib: FuncAnimation](https://matplotlib.org/stable/api/_as_gen/matplotlib.animation.FuncAnimation.html) | A callback receives successive values from an iterable or generator. Frame-data caching is configurable. | A solver-state iterator and drawing callback are a reasonable small-script API; avoid unbounded trace retention. |
| [pyglet: time](https://pyglet.readthedocs.io/en/latest/programming_guide/time.html), [event loop](https://pyglet.readthedocs.io/en/latest/programming_guide/eventloop.html) | Scheduled updates receive elapsed time; an application loop dispatches input and drawing events. | State updates, presentation, and input scheduling deserve distinct contracts. |
| [Python typing: protocols](https://typing.python.org/en/latest/spec/protocol.html) | Structurally compatible objects can implement an interface without inheriting a particular class. | Describe the engine's effect interface with a protocol while allowing an optional helper base class. Static typing does not replace runtime validation. |
