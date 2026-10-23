# bruhanimate

**Composable terminal animations for Python.**

[![PyPI](https://img.shields.io/pypi/v/bruhanimate)](https://pypi.org/project/bruhanimate/)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://pypi.org/project/bruhanimate/)
[![CI](https://github.com/ethanlchristensen/bruh.animate/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/ethanlchristensen/bruh.animate/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/ethanlchristensen/bruh.animate/blob/main/LICENSE)

[Documentation](https://ethanlchristensen.github.io/bruh.animate/) ·
[Getting started](https://ethanlchristensen.github.io/bruh.animate/getting_started.html) ·
[Core concepts](https://ethanlchristensen.github.io/bruh.animate/concepts.html) ·
[Release guide](https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md)

Turn a simulation, drawing function, or stream of solver snapshots into an ASCII
animation. One player handles timing, input, changed-cell rendering, and terminal
cleanup, so your code can concentrate on what happens and how it looks.

- **Built-in effects:** snow, fire, rain, stars, Matrix, cellular automata, and more.
- **Layered scenes:** combine animated backgrounds, text, and custom drawings.
- **Solver playback:** pause, step, and change speed while consuming snapshots lazily.
- **Grid helpers:** board coordinates, centered layouts, paths, markers, and clipping.

> **Version 1 is a breaking release.** The old renderer hierarchy is replaced by
> `play`, `Scene`, and `Playback`. See the [migration guide](https://ethanlchristensen.github.io/bruh.animate/migration.html).

## Quick start

Requires Python 3.13 or newer. After a 1.x release is published:

```sh
python -m pip install "bruhanimate>=1,<2"
```

For unreleased code, use the [source checkout](#development). Optional audio
capture dependencies are available with `python -m pip install "bruhanimate[audio]>=1,<2"`.

Save this as `animation.py` and run `python animation.py` in a terminal:

```python
from bruhanimate import play

play("snow", preset="light", fps=60, updates_per_second=30)
```

Press **q**, **Escape**, or **Ctrl+C** to quit and restore the terminal.
`fps` controls presentation; `updates_per_second` controls simulation ticks.
Set `frames=120` to limit the number of presented frames.

## Discover effects and presets

`light` is a named `SnowSettings` configuration: intensity `0.005`, wind `0.0`,
with collision and info display disabled. Discover the choices and their values:

```python
from bruhanimate import effects

print(effects.names())             # All registered effects
print(effects.snow.presets())      # light, moderate, blizzard, windy + settings
print(effects.snow.preset("light")) # A fresh SnowSettings copy
print(effects.snow.defaults())     # Default settings, with typed fields
```

For editor completion of effects, effect-specific presets, and settings, use
the typed catalog. It runs through the same player as `play("snow", ...)`:

```python
from bruhanimate import effects

effects.snow.play(preset="light", fps=60, updates_per_second=30, duration=10)
```

`duration` limits wall-clock seconds after startup, including paused/held time.
The first duration, frame, completion, or quit condition wins. Zero starts no
effect; `play` still opens/restores its Screen. Slow callbacks can overrun the
deadline. Built-in settings validate types, ranges, and choices before use.

Explore without writing a script or opening an animation:

```sh
bruhanimate list
bruhanimate presets snow
bruhanimate info snow
bruhanimate play snow --preset light --duration 10 --set wind=0.4
```

`python -m bruhanimate` provides the same CLI. In a source checkout, prefix either
command with `uv run --locked`. See the [discovery guide](docs/source/discovery.rst)
for configuration, CLI options, typing, and custom registry entries.

## Capture and record

Use a seed to reproduce an effect with the same settings, size, update sequence,
and dependency versions. Each effect has independent Python/NumPy randomness.
The typed catalog also exposes headless capture and recording:

```python
from bruhanimate import Frame, effects

def inspect(frame: Frame) -> None:
    print(frame.index, frame.time, frame.text())

effects.snow.capture(on_frame=inspect, preset="light", seed=42,
                     width=40, height=12, frames=4)
```

```sh
bruhanimate record snow snow.cast --preset light --seed 42 --duration 5
```

Capture uses virtual time and requires a frame or duration bound. It streams
immutable snapshots through the existing player without opening a terminal or
sleeping. `effects.snow.record("snow.cast", ...)` writes asciicast v2 files;
existing files are protected unless `overwrite=True` / `--overwrite` is set.
Live audio still requires matching external input for repeatability. See the
[capture guide](docs/source/capture.rst) for timing, ownership, and format details.

## Build a scene

Layers support `region=(x, y, width, height)` clipping and independent
`updates_per_second` rates. `TimedOverlay` shows a child for a limited duration,
then reveals the current layers beneath it. For a complete example using all
three features, run the native beam demo:

```python
from bruhanimate import beam_demo

beam_demo.run(frames=180, fps=60)
```

It combines snow at 15 updates/sec, a lazy beam solver at 5 steps/sec, a temporary
message, and a status display. Space pauses the solver, n/right steps, +/- changes
speed, and q quits. See the [composition guide](docs/source/composition.rst) for
typed API examples, clipping coordinates, timing, and ownership.

For a visual composition example, run a retro TV showing colorful plasma with
snow falling behind its opaque cabinet. A channel badge disappears after two
seconds; the TV keeps playing until q or the frame limit:

```python
from bruhanimate import tv_demo

tv_demo.run(frames=180, fps=60)
```

Or run `python -m bruhanimate.demos.tv_demo` in your terminal.
See [the TV demo](docs/source/demos/tv_demo.rst) for the layer layout.

For four windows bouncing around the terminal, each with its own effect:

```python
from bruhanimate import windows_demo

windows_demo.run(frames=180, fps=60)
```

Run `python -m bruhanimate.demos.windows_demo` for continuous playback.
Plasma, fire, snow, and Matrix rain move with their frames and overlap in a fixed
stacking order. See [the moving windows demo](docs/source/demos/windows_demo.rst).

Use `Panel` to compose your own movable windows. `size` is the content size;
the border adds two columns and two rows. The factory receives the correct local
buffer, and typed settings/presets remain available through `effects.snow`:

```python
from bruhanimate import Panel, SnowEffect, effects, play

def build(buffer):
    return Panel(
        effect_factory=lambda local: SnowEffect(local, " ", effects.snow.preset("light")),
        size=(28, 8),
        position=(2, 2),
        velocity=(18, 3),
        bounds=(0, 0, buffer.width(), buffer.height()),
        bounce=True,
        border=True,
        title="Snow",
        updates_per_second=15,
    )

play(effect_factory=build, fps=60, updates_per_second=60, frames=180)
```

Type `Panel(` for named options and `effects.snow.preset(` for preset completion.
See the [Panel guide](docs/source/panels.rst) for clipping, transparency, and ownership.

## Build a dashboard

`Row` and `Column` allocate `Slot`s using `Fixed` cell counts or weighted `Flex`
space. Nest containers without calculating coordinates. Labels support typed
alignment, clipping, wrapping, and styling; callbacks refresh text during updates.

```python
from bruhanimate import Column, Fixed, Flex, Label, Row, Slot, Spacer, StatusBar, TextStyle, play

layout = Column(
    Slot(Label("MY DASHBOARD", align="center", style=TextStyle(bold=True)), size=Fixed(1)),
    Slot(Row(
        Slot(Label("Main content", align="center", vertical_align="middle"), size=Flex(2)),
        Spacer(Fixed(1)),
        Slot(Label(lambda: "State: ready", overflow="ellipsis"), size=Fixed(16)),
    )),
    Slot(StatusBar("Ready", right="q quit", style=TextStyle(background=24)), size=Fixed(1)),
    padding=1,
    gap=1,
)
play(effect_factory=layout.build, fps=60, frames=180, on_resize="resize")
```

Use `Slot(effect_factory=...)` for animations that need an allocated local buffer.
Type `Label(..., align=...)` or `overflow=...` for editor choices. Layout trees
are single-use; create a new tree for another run. See the
[layout and text guide](docs/source/layouts.rst) for sizing, ownership, and callbacks.

Run `python -m bruhanimate.demos.dashboard_demo` for a beam solver, live statistics,
snow background, plasma preview, and an activity log. Tab/Shift+Tab selects a panel;
Space pauses the solver or signal. In the solver, n steps and +/- changes speed; in the signal
panel, r remixes plasma. The focused border and status hints show where keys go.
Arrows/Page Up/Down/Home/End scroll the solver or log. Scrolling upward in the log
suspends following new messages; End resumes it. The log records solver progress
and control actions, with bounded history.
q quits. Resize the terminal while paused to see the layout reflow
without losing the solver snapshot or queued steps. See the [dashboard demo](docs/source/demos/dashboard_demo.rst).

## Keyboard bindings and focus

Named keys are Literal-typed for editor completion. Character shortcuts use
`KeyBinding.character(...)`. Attach a target to each interactive panel, then pass
the group's handler to the existing player:

```python
from bruhanimate import (
    Column, Fixed, FocusGroup, FocusTarget, KeyBinding, KeyBindings,
    Label, Panel, Slot, StatusBar, play,
)

state = {"count": 0}

def increment() -> None:
    state["count"] += 1

counter = FocusTarget("counter", KeyBindings(
    KeyBinding("space", increment, description="increment"),
))
focus = FocusGroup(counter)
layout = Column(
    Slot(Panel(Label(lambda: f"Count: {state['count']}"),
               size=(20, 3), fit=True, title="Counter", focus=counter)),
    Slot(StatusBar("counter", center=focus.help_text, right="q quit"), size=Fixed(1)),
)
play(effect_factory=layout.build, event_handler=focus.handle_event,
     frames=180, on_resize="resize")
```

Add more targets to `FocusGroup` to navigate with Tab/Shift+Tab. Bindings expose
typed `hints()` and `help_text()` so help stays aligned with actions. Actions return
None and consume their key; `quit=True` explicitly requests exit. FocusGroup adds
q/Q, Escape, and Ctrl+C as global fallback quit keys. Hidden or disabled targets
are skipped, and showing a panel does not steal focus. See the
[keyboard guide](docs/source/keyboard.rst) for custom navigation, global bindings,
visibility, and `EventResult` for custom routing.

## Scrollable content and logs

`ScrollView(animation, size=(40, 8), content_size=(100, 60))` owns an animation on
a larger canvas. Its viewport resizes without restarting the child or consuming
solver snapshots. `LogView` stores bounded text history and exposes the same
scrolling controls:

```python
from bruhanimate import (
    Column, Fixed, FocusGroup, FocusTarget, LogView, Panel, Slot, StatusBar, play,
)

log = LogView(size=(40, 6), max_lines=200, wrap="character", follow_tail=True)
log.append("Ready\n" + "\n".join(f"Activity {i}" for i in range(20)))
target = FocusTarget("activity", log.bindings)
focus = FocusGroup(target)
layout = Column(
    Slot(Panel(log, size=(40, 6), fit=True, title="Activity", focus=target)),
    Slot(StatusBar(lambda: "LIVE" if log.follow_tail else "HISTORY",
                   center=focus.help_text, right="q quit"), size=Fixed(1)),
)
play(effect_factory=layout.build, event_handler=focus.handle_event,
     on_resize="resize", frames=180)
```

Append messages from actions or updates. `wrap` offers typed `"character"` and
`"none"` choices; `TextStyle` controls colors. Upward scrolling preserves your place
as messages arrive; End or `log.follow_tail = True` returns to the newest messages.
`max_lines` counts logical lines, and evicts the oldest excess lines. The
[scrolling guide](docs/source/views.rst) covers resize anchoring, navigation,
ownership, and an interactive append example.

## Live terminal resize

Live resize is opt-in with `on_resize="resize"` on `play`, `Player`, or
`effects.snow.play`. Editors suggest both `"raise"` (the existing default) and
`"resize"` through `ResizePolicy`. Layouts reflow; `Panel(..., fit=True)` follows
its parent's allocation. Snow piles and fire follow the new bottom; plasma fills
the new area at its current phase. Rain preserves drops and lightning lifetimes,
and Matrix preserves characters and row timing. Cropped state is discarded;
other built-ins retain their original simulation size and clip on shrink. Custom
animations can implement the same typed `Resizable.resize((width, height))` hook. See the
[resize guide](docs/source/resize.rst) for lifecycle and platform details.

```python
from bruhanimate import effects

effects.fire.play(on_resize="resize", fps=60, updates_per_second=30, frames=180)
# The same option is available on effects.rain.play() and effects.matrix.play().
```


Put a title over an animated background:

```python
from bruhanimate import ImageEffect, Scene, effect_registry, play


def build(buffer):
    snow = effect_registry.create("snow", buffer, " ", preset="light")
    return Scene(snow, ImageEffect("Advent of Code"))


play(effect_factory=build, fps=60, updates_per_second=30)
```

The factory receives a screen-sized buffer. A scene paints its children from back
to front, and `ImageEffect` centers text by default. Use
`Layer(animation, transparent=True)` when plain spaces should reveal lower layers;
`None` cells are always transparent.

## Animate a solver

Yield snapshots from your solver and describe how to draw one:

```python
from bruhanimate import Playback, draw_grid, play

board = ("S...", ".##.", "...E")


def states():
    yield from ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2))


def draw(position, buffer):
    grid = draw_grid(buffer, board, spacing=(2, 1))
    grid.put(*position, "@")


animation = Playback(states(), draw, steps_per_second=5)
play(animation, fps=60, event_handler=animation.handle_event, on_complete="hold")
```

**Space** pauses, **n/right arrow** steps, **+/-** changes speed, and **q** quits.
The final state stays visible; use `on_complete="exit"` to close automatically.
Yield independent snapshots, and keep the work between yields short enough for
responsive input. Playback keeps the current snapshot and closes its iterator on
completion or early quit.

## Choose the right building block

| You want to… | Start with |
| --- | --- |
| Run a built-in effect | `play("fire")` or a named preset |
| Write a small custom animation | `CallbackEffect(draw, update=update)` |
| Keep a persistent simulation raster | Subclass `BaseEffect` and implement `update(dt)` |
| Combine backgrounds, labels, and overlays | `Scene`, `Layer`, and `ImageEffect` |
| Pan a board or larger animation canvas | `ScrollView` |
| Browse bounded activity history | `LogView` |
| Route keys to a selected panel | `FocusTarget` and `FocusGroup` |
| Animate a solver or recorded states | `Playback` and `draw_grid` |
| Supply your own Screen or clock | `Player` |

Change state in `update(dt)` and read it in `draw(buffer)`. The player owns the
loop; animations own their state. The [core-concepts guide](https://ethanlchristensen.github.io/bruh.animate/concepts.html)
walks through this division with complete examples.

## Explore the demos

```sh
python -m bruhanimate.demos.snow_demo
python -m bruhanimate.demos.fire_demo
python -m bruhanimate.demos.shared_player_demo
python -m bruhanimate.demos.grid_demo
```

From a uv source checkout, prefix these commands with `uv run --locked`.
The grid demo includes a complete BFS solver, animated background, status text,
and playback controls. Demos expose `run(frames=None, fps=...)` for use from Python.

## Documentation

| Guide | What it covers |
| --- | --- |
| [Getting started](https://ethanlchristensen.github.io/bruh.animate/getting_started.html) | Installation, first animation, and demos |
| [Core concepts](https://ethanlchristensen.github.io/bruh.animate/concepts.html) | Player, state, buffers, composition, and solver snapshots |
| [Player and composition](https://ethanlchristensen.github.io/bruh.animate/player.html) | Timing, lifecycle, ownership, and the API |
| [Solver playback](https://ethanlchristensen.github.io/bruh.animate/playback.html) | Pause, stepping, completion, and bounded solver work |
| [Migration to 1.0](https://ethanlchristensen.github.io/bruh.animate/migration.html) | Replacing the 0.2.x renderer APIs |
| [Release process](https://ethanlchristensen.github.io/bruh.animate/releasing.html) | Dev-to-main workflow, versions, tags, and publishing |

Resize currently ends playback after cleanup; automatic reflow and image/video
export remain planned work. Headless frame capture and `.cast` export are supported.
The terminal demo is a pipe-based command console, not a PTY emulator.

## Development

Use Python 3.13 and uv 0.13.4, pinned in `pyproject.toml`:

```sh
git clone https://github.com/ethanlchristensen/bruh.animate.git
cd bruh.animate
git switch dev
uv sync --locked --group docs
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
uv run --locked python scripts/check_examples.py
uv run --locked --group docs python scripts/build_docs.py
```

Install uv with `python -m pip install uv==0.13.4`, or update an existing standalone
installation with `uv self update 0.13.4`. Sync installs this checkout in editable
mode. Open `docs/build/html/index.html` to preview the documentation.

Read [AGENTS.md](https://github.com/ethanlchristensen/bruh.animate/blob/main/AGENTS.md)
for architecture, lifecycle rules, and contribution checks. CI tests Linux,
Windows, and macOS and smoke-tests installed wheel/source distributions.

## Releases

**Work on dev → merge into main → wait for green CI → push a matching version tag.**

A merge updates the documentation site. Pushing `vMAJOR.MINOR.PATCH` starts package
validation and publishing to PyPI, followed by a GitHub release. The preparation
helper previews by default and never creates a tag:

```sh
# Check the currently prepared version; no version or Git changes:
uv run --locked python publish.py --check
```

Follow the [complete release checklist](https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md)
for version/lockfile agreement, authentication setup, tag commands, and recovery.

## License

[Apache 2.0](https://github.com/ethanlchristensen/bruh.animate/blob/main/LICENSE).
Created by Ethan Christensen, with inspiration from
[Asciimatics](https://github.com/peterbrittain/asciimatics).
