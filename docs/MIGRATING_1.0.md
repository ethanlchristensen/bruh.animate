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
