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

## Build a scene

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

Resize currently ends playback after cleanup; automatic reflow and recording/export
remain planned work. The terminal demo is a pipe-based command console, not a PTY
emulator. See the [roadmap](https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/ROADMAP.md)
for implementation status and remaining Advent of Code helpers.

## Development

Use Python 3.13 and uv 0.13.4, pinned in `pyproject.toml`:

```sh
git clone https://github.com/ethanlchristensen/bruh.animate.git
cd bruh.animate
git switch dev
uv sync --locked --group docs
uv run --locked ruff check .
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
