# bruhanimate

[![Downloads](https://static.pepy.tech/badge/bruhanimate)](https://pepy.tech/project/bruhanimate)

Terminal animations for Python 3.13+. Built-in simulations, custom drawing callbacks,
and layered scenes all run through one player.

The **1.x API** is a breaking change from 0.2.x. See the
[migration guide](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/MIGRATING_1.0.md) for changes from 0.2.x.

## Install

```sh
pip install --upgrade "bruhanimate>=1,<2"
# Optional audio capture dependencies:
pip install --upgrade "bruhanimate[audio]>=1,<2"
```

For unreleased changes, install the source checkout with `pip install .` or
`pip install ".[audio]"`. The commands above require a published 1.x release.

## Play an effect

```python
from bruhanimate import SnowSettings, play

play("snow", settings=SnowSettings(intensity=0.02, wind=0.2),
     fps=60, updates_per_second=30)
```

`q`, Escape, or Ctrl+C exits and restores the terminal. `frames=120` limits
presentations. `fps` controls drawing; `updates_per_second` controls simulation.
Without an explicit update rate, the player updates once per presentation.
Built-in simulations advance one step per tick; their settings use tick units.

Discover effects and presets:

```python
from bruhanimate import effect_registry

for name, entry in effect_registry.entries().items():
    print(name, entry.description, list(entry.presets))
```

Registered effects: `audio`, `automaton`, `boids`, `diffusion`, `drawlines`, `fire`,
`firework`, `gol`, `julia`, `matrix`, `noise`, `offset`, `perlin`, `plasma`, `rain`,
`sand`, `snow`, `stars`, `static`, `twinkle`, and `voronoi`.

## Compose content

```python
from bruhanimate import ImageEffect, Scene, effect_registry, get_image, play

def build(buffer):
    return Scene(
        effect_registry.create("snow", buffer, " ", preset="light"),
        ImageEffect(get_image("bruh")),
    )

play(effect_factory=build, fps=60, updates_per_second=30)
```

Scenes paint from back to front. `None` cells reveal lower layers; wrap an
animation in `Layer(animation, transparent=True)` to reveal them through plain
spaces too. `ImageEffect` centers by default, supports explicit x/y coordinates,
and accepts a velocity in cells per second for panning.

`get_image()` retrieves bundled ASCII art. `text_to_image()` uses PyFiglet;
it does not load raster image files.

## Draw your own animation

```python
from bruhanimate import CallbackEffect, play

state = {"step": 0}

def update(dt):
    state["step"] += 1

def draw(buffer):
    buffer.put_at_center(buffer.height() // 2, f"Puzzle step: {state['step']}")

play(CallbackEffect(draw, update=update), fps=60, updates_per_second=10)
```

Advance the puzzle in `update`, and only read its state in `draw`. For persistent
raster simulations, subclass `BaseEffect` and implement `update(dt)`; its default
`draw` copies the current raster without advancing it. Use an effect factory to
receive a correctly sized private buffer.

## Animate solver snapshots

```python
from bruhanimate import Playback, draw_grid, play

board = ("S...", ".##.", "...E")

def states():
    yield from ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2))

def draw(position, buffer):
    grid = draw_grid(buffer, board, spacing=(2, 1))
    grid.put(*position, "@")

animation = Playback(states(), draw, steps_per_second=5)
play(animation, fps=60, event_handler=animation.handle_event, on_complete="exit")
```

Space pauses, n/right steps, +/- changes speed, and q quits. Playback consumes
states lazily and closes its iterator on exhaustion or early quit. Grid drawing
handles centering, spacing, camera offsets, and clipping. See the
[solver playback guide](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/SOLVER_PLAYBACK.md) for snapshots and completion.

## Demos and documentation

```sh
python -m bruhanimate.demos.snow_demo
python -m bruhanimate.demos.shared_player_demo
python -m bruhanimate.demos.grid_demo
python -m bruhanimate.demos.terminal_demo
```

All demos expose `run(frames=None, fps=...)`. The terminal demo is a pipe-based
command console: Escape exits and printable `q` goes to the shell. It does not
emulate a PTY or interpret terminal escape sequences.

- [Solver playback and grid drawing](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/SOLVER_PLAYBACK.md)
- [Player, lifecycle, and composition guide](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/PLAYER.md)
- [1.0 migration guide](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/MIGRATING_1.0.md)
- [Architecture decisions](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/DESIGN_PROPOSAL.md)
- [Roadmap and remaining AoC helpers](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/ROADMAP.md)

Inspired by [Asciimatics](https://github.com/peterbrittain/asciimatics).
Licensed under Apache 2.0; see [LICENSE](https://github.com/FNBBDevs/bruhanimate/blob/main/LICENSE).

## Contributing and releasing

Use Python 3.13 and uv 0.13.4. Start with [AGENTS.md](https://github.com/FNBBDevs/bruhanimate/blob/main/AGENTS.md) for architecture
and contribution conventions, and keep public docstrings/examples synchronized.

```sh
python -m pip install uv==0.13.4
uv sync --locked --group docs
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python scripts/check_examples.py
uv run --locked --group docs python scripts/build_docs.py
```

For an existing standalone uv installation, update with `uv self update 0.13.4`.

CI tests Linux, Windows and macOS, verifies source/installed packages, and builds
Sphinx documentation strictly. The committed uv.lock pins contributor and CI
environments without pinning consumers to that environment.
uv handles the development workflow and builds; `poetry-core` remains only as the
build backend. Publishing uses the PyPA action for Trusted Publishing attestations.

**Publishing is tag-driven:** merging into main does not publish to PyPI. The
release workflow validates a matching vMAJOR.MINOR.PATCH tag on a main-branch
commit and publishes the tested distributions. The publish helper previews by
default; write/commit/push/PR operations require explicit flags.

```sh
# Validate the currently prepared 1.0.0 without bumping it:
uv run --locked python publish.py --check
# Preview a future release:
uv run --locked python publish.py 1.1.0
```

Read the [release guide](https://github.com/FNBBDevs/bruhanimate/blob/main/docs/RELEASING.md) for tag commands, Trusted Publishing
or existing-token setup, environment requirements and retry procedures.
