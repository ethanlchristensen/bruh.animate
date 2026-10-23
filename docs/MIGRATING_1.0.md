# Migrating to bruhanimate 1.0

1.0 intentionally breaks the 0.2.x rendering API. This checkout is prepared for
1.0.0; publication is a separate step. Built-in effects and all packaged demos
use the native Animation contract. There are no compatibility adapters.

## Launch code

```python
# 0.2.x
from bruhanimate import EffectRenderer, Screen

def demo(screen):
    EffectRenderer(screen, frames=120, frame_time=0.05, effect_type="snow").run()

Screen.show(demo)
```

```python
# 1.0
from bruhanimate import play
play("snow", frames=120, fps=20, updates_per_second=20)
```

Use `None` for unlimited frames instead of `float("inf")`. FPS replaces
`frame_time`; an explicit update rate controls simulation separately. Exit is
prompt-free. Registry names and settings classes remain available except for
unfinished water, which is removed rather than advertised as an effect.

## Custom effects

Replace `render_frame(frame_number)` with `update(dt)`. Keep any logical tick
counter your algorithm needs in the effect itself. `BaseEffect.draw(buffer)`
copies the persistent simulation raster without advancing it. Code that needs
continuous motion should accumulate dt in seconds instead of presentation frames.
`BaseEffect` now enforces its abstract update method at construction.

Pass custom effects through `play(effect_factory=YourEffect)`; the factory
receives a screen-sized Buffer. Do not build a dummy static renderer and replace
its effect. Direct Animation objects and `CallbackEffect` also work without
registration. See [the player guide](PLAYER.md) for complete examples.

## Renderer responsibilities

The entire `bruhanimate.bruhrenderer` package and its root exports are removed.

| Old use | 1.0 approach |
| --- | --- |
| `EffectRenderer` / `BaseRenderer` loop | `play` or `Player` |
| `CenterRenderer` | `Scene(background, ImageEffect(rows))` |
| `PanRenderer` | `ImageEffect(rows, x=..., y=..., velocity=(vx, vy))` |
| `BackgroundColorRenderer` | Draw styled cells with `CallbackEffect`, then compose in a Scene |
| `TerminalRenderer` | `TerminalEffect` in a Scene; pass its handle_event to Player |
| `FireworkEffect.set_second_effect` | An independent lower Scene layer |
| `render_to_back_buffer`, `swap_buffers`, `present_frame` | Player handles drawing, diffing, batching, and rotation |
| End-message prompt | Add explicit application UI after playback if needed |

The old FocusRenderer character-assembly algorithm is removed; it has no built-in
replacement yet. Implement assembly as an Animation if required. Panning uses
elapsed-time velocity and clips rather than reproducing old looping semantics.
Image collision is no longer inferred by a renderer: configure effect collision
inputs explicitly. There is no automatic collision coupling between Scene layers.

A Scene paints from back to front. `None` reveals lower layers. Plain spaces are
opaque unless the corresponding `Layer` sets `transparent=True`; replace old
`smart_transparent` flags with explicit layer transparency.

## Lifecycle

Construction and demo imports open no runtime resources. Player owns the supplied
animation by default, calling start and close even after partial startup failure.
Use `manage_effect=False` only with already started instances whose lifecycle you
own. Scene owns its children; do not share an instance between owners.

Audio capture starts in `start()`, not the constructor. Call start/close yourself
when running effects outside Player. Terminal subprocesses, reader threads, and
owned descendants are cleaned up on close. Screen.show handles terminal restoration.

## Demo entry points

`python -m bruhanimate.demos.snow_demo` and `from bruhanimate import snow_demo`
continue to work. All demos now expose `run(*, frames=None, fps=...)` without a
Screen argument; use Player directly to supply an existing Screen. Multi-phase
demos cycle configurations through one player and quit as a whole on q/Escape.
The terminal console uses Escape to quit and accepts q as printable shell input.

## Reliability changes included

Partial clears clip without changing buffer dimensions. Nonpositive clear sizes
are no-ops. Negative buffer dimensions and incompatible copies raise ValueError.
Rain defaults/presets now generate visible rain, snow honors zero and low spawn
probabilities, color presets/demos use valid palettes, and tiny positive canvases
avoid known lightning/firework/audio failures. Zero-sized effect canvases remain
unsupported. Utility effect lists no longer advertise nonexistent chat/water.


## Duration, discovery, and validation milestone (unreleased)

- `play` and `Player` accept `duration` in wall-clock seconds after startup.
  Pauses/hold count toward it. Zero starts no effect; callbacks can overrun.
- `from bruhanimate import effects` exposes statically typed built-in catalog
  members, for example `effects.snow.play(preset="light", duration=10)`.
  Existing string-based calls and custom registry registration remain supported.
- `bruhanimate` and `python -m bruhanimate` provide `list`, `presets`, `info`, and
  `play` commands, including repeatable `--set FIELD=VALUE` overrides.
- Built-in settings now raise `TypeError` for incorrect types and `ValueError`
  for invalid ranges/choices, non-finite numbers, and unsupported glyphs. They
  no longer rely on constructor clamping or silent fallback. Fix invalid values
  at configuration time. Existing individual runtime setters retain their
  documented behavior. NoiseSettings(intensity=0) now disables new noise.
- Explicit settings still take precedence over a preset, but the supplied preset
  must exist. Settings for effects without a settings class are rejected, and
  settings must match the registered class. Unknown presets list valid choices.
- `effect_registry.presets()` now copies nested values as well as the mapping.
  Editing the result no longer mutates registered presets.
- Unsupported offset `up`/`down` presets are removed. They previously silently
  selected `right`; choose `left` or `right` explicitly.

See [discovery](source/discovery.rst) for editor completion and settings ranges.

## Seeded capture milestone (unreleased)

- All built-in settings gain a keyword-only `seed: int | None`, preserving existing
  positional fields. Non-negative seeds select independent Python/NumPy streams.
  Global `random.seed` and `numpy.random.seed` no longer control effects. Configure
  `SnowSettings(seed=42)` or use `effects.snow.play(seed=42, ...)` instead.
- Diffusion previously hard-coded a NumPy seed of zero. Its default now uses fresh
  entropy like the other simulations; select `DiffusionSettings(seed=0)` to retain
  the old initialization. Seeds reproduce fresh effects with matching inputs,
  sizes, timing and dependency versions; they do not rewind existing instances.
- `capture` streams immutable `Frame` snapshots; `record` streams asciicast v2 to
  a path or borrowed text stream. Both use Player with virtual time and require
  `frames` or `duration`. Completion exits by default. They own supplied content
  and close it on failure, but do not disable resource acquisition in `start()`.
- The typed catalog adds matching `.capture()` / `.record()` methods; the CLI
  adds `record` and `--seed`. Existing files require explicit overwrite. Named
  effect seed overrides copy settings/presets; static/Julia reject these overrides.

See [capture and recording](source/capture.rst) for timing and format contracts.
