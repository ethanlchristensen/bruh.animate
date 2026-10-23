# Solver playback and grid drawing

The solver produces snapshots; drawing reads a snapshot; `Playback` controls
when to request the next one. Neither the solver nor the drawing callback needs
to open a terminal or implement a renderer subclass.

## A complete small example

```python
from bruhanimate import Playback, draw_grid, play

board = ("S...", ".##.", "...E")

def states():
    # Replace this path with your solver's lazy state generator.
    yield from ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2))

def draw(position, buffer):
    grid = draw_grid(buffer, board, spacing=(2, 1))
    grid.put(*position, "@")

animation = Playback(states(), draw, steps_per_second=5)
play(animation, fps=60, event_handler=animation.handle_event, on_complete="exit")
```

The same generator can be consumed in a normal Python loop without a Screen.
For a working BFS solver with immutable snapshots, an animated background,
status text, and a final solution path, run:

```sh
python -m bruhanimate.demos.grid_demo
```

The demo uses its own small public fixture. Puzzle input files and puzzle-specific
branching rules stay in application code. Loading failures should propagate;
the library does not select a fallback input file.

## Controls and time

Pass `event_handler=animation.handle_event` explicitly. It replaces the player's
default quit handling and provides:

| Key | Action |
| --- | --- |
| Space or p | Pause/resume solver consumption |
| n, right arrow, or . | Pause and request one logical step |
| + or = | Faster (up to 240 states/second through keyboard controls) |
| - or _ | Slower (down to 0.25 states/second through keyboard controls) |
| q/Q, Escape, Ctrl+C | Quit |

`animation.pause()`, `resume()`, and `step()` expose the same controls to code.
`step()` queues consumption for update; it never calls the solver during input
polling. Set `paused=True` to wait for a step before reading the first snapshot.
Programmatic `steps_per_second` accepts any positive finite rate.

Playback advances immediately on its first unpaused update, then uses accumulated
dt to schedule states. Repeated draws never call next(). Paused time is discarded
on resume and speed changes. Catch-up consumes at most `max_catch_up` states per
update (default five), dropping excess accumulated time after a stall.

FPS still controls presentation. An explicit Player `updates_per_second` controls
how often all scene children update; Playback's `steps_per_second` independently
controls solver consumption. Set the player's update rate at least as high as the
solver rate when each intermediate snapshot should receive its own draw. Multiple
solver steps between presentations display only the latest snapshot.

Pause affects this Playback instance, so unrelated background effects can keep
animating. There is no global pause, rewind, or arbitrary seeking yet.

## Snapshots, bounds, and ownership

Construction and start do not advance the source. Playback stores only the current
snapshot, with no lookahead or trace cache. `state`, `has_state`, `steps`, `paused`,
and `finished` report progress. A yielded None is a valid state; `has_state`
distinguishes it from a source that has not yielded anything.

By default the snapshot is borrowed without copying. Yield independent immutable
values, or pass `copy_state=deepcopy` if the producer reuses mutable objects. The
drawing callback must treat its state as read-only. The source may itself retain
solver data; Playback cannot make an eager source or its search tree bounded.

Playback is single-use. It acquires an iterator at start and calls that iterator's
optional close method on exhaustion or cleanup, including early quit and errors.
Generator finally blocks therefore run on early stop. Build a fresh Playback and
source to replay. Manage any additional resources held outside the iterator in
application code or an explicit Animation lifecycle.

`next()` runs synchronously. Bounded catch-up limits the number of calls, not the
duration of one call: a solver must yield bounded units of work to keep input
responsive. For large searches, yield aggregated counters or sampled progress
and enforce a work/state limit inside the producer. Do not enumerate an
exponential search trace simply to animate it. Sampling must still leave short
enough work intervals between yields. Worker execution remains future work.

## Completion

`on_complete="hold"` is the default: keep the final snapshot visible, continue
drawing backgrounds, and poll input. `on_complete="exit"` restores the terminal
after presenting completed content. A source is known to be exhausted only when
the next scheduled advance raises StopIteration; there is no prefetch. An empty
source presents one cleared/background frame before exiting.

Playback sets `finished=True` on exhaustion and closes the iterator while keeping
the last snapshot for drawing. Early quit/close does not report completion.
Scene completes when all children that expose a non-None finished status complete;
endless backgrounds are ignored. A scene containing only endless content reports
None and never triggers automatic completion. Nested scenes follow the same rule.

Use a normal status drawing callback for completion messages. `frames` remains
a presentation limit independent of solver completion. `duration` limits Player
wall-clock seconds after startup (virtual seconds in headless capture).
Automatic source restart remains future work.

## Grid viewport

`draw_grid(buffer, rows, **layout)` draws a rectangular board and returns a
`GridViewport` for additional paths, text, and markers. Cell styling can be a
mapping of values to glyphs or a callback `glyph(value, column, row)`.

```python
from bruhanimate import Buffer, draw_grid

buffer = Buffer(10, 30)
board = ("S...", ".##.", "...E")
grid = draw_grid(buffer, board, spacing=(2, 1),
                 region=(0, 1, buffer.width(), buffer.height() - 2))
grid.path(((0, 0), (1, 0), (2, 0)), "*")
grid.put(3, 2, "@")
grid.text(0, 1, "GO")
screen_x, screen_y = grid.to_screen(3, 2)
```

`spacing=(2, 1)` places glyph anchors two terminal columns and one row apart.
A fitting board centers in its region; an oversized board anchors at the region's
top left. `camera=(column, row)` scrolls the board in logical cells. Explicit x/y
are absolute screen origins, including zero and negative positions. Region is
`(x, y, width, height)` and clips all grid drawing along with Buffer bounds.

`GridViewport.from_rows(buffer, rows, **layout)` creates the transform without
drawing, while `GridViewport(buffer, columns, rows, **layout)` supplies dimensions
directly. `to_screen` transforms without clipping. `put` returns whether a cell
was painted. `path` paints supplied points; it does not interpolate vertices.
`text` advances through board cells using the configured spacing.

Ragged rows and mismatched shapes raise ValueError. Empty boards and empty regions
draw nothing. Offscreen cells do not invoke glyph callbacks. None is transparent;
a plain space paints and clears the cell. Mapping to an ANSI SGR styled glyph
supports colors including code 0. Include a reset when styling raw strings.

Glyphs must contain one printable cell, optionally with SGR color/reset sequences.
Wide characters, combining marks, controls, multiple visible characters, and raw
cursor escapes are rejected. Ambiguous-width characters such as box drawing
assume a one-cell terminal; full grapheme/terminal-width handling is deferred.
Grid drawing does not fill gaps between spaced cells or clear the destination.
Player and Scene provide fresh drawing buffers for composition.


## Terminal resize

Use `play(..., on_resize="resize")` with a layout containing your existing
Playback instance. Layout reflow retains the iterator, current snapshot, pause
state, speed, queued manual steps and solver clock. Resizing alone never calls
`next()`. A started solver continues receiving updates when its slot is hidden;
a paused solver stays paused. Do not rebuild or re-own Playback in a resize
callback. `dashboard_demo` demonstrates shrinking and growing a paused solver.

The dashboard now uses `FocusGroup` to route controls: Tab/Shift+Tab selects the
solver, signal, or activity log panel, and Space pauses the solver or signal.
Solver n queues a step and +/- changes speed; signal r remixes plasma. It binds the public
Playback methods without advancing the iterator during input or drawing. The
status bar reads help from the focused bindings. Hidden layout slots lose focus
without resetting Playback state. See the [keyboard guide](source/keyboard.rst).

The dashboard wraps Playback in a `ScrollView` with a fixed full-board canvas.
Arrows/Page Up/Down/Home/End pan it without advancing the iterator. Its `LogView`
records progress after updates, plus control actions, and retains 200 logical
lines. When the log has focus, those keys scroll history instead. Upward scrolling
suspends automatic scrolling; End resumes following new messages. The original
standalone `Playback.handle_event` still uses Right to step; the dashboard uses
Right for horizontal panning. See [scrollable views](source/views.rst).
See the [resize guide](source/resize.rst) for fitting panels and custom views.
