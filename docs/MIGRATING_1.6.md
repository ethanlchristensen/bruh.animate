# Migrating to 1.6.0

Version 1.6.0 adds object, game, control and TUI APIs alongside new procedural
effects. Most additions require no migration; the behavior corrections below
may require caller changes.

`FlowEffect`, `GrowthEffect` and `StarfieldEffect` are additive, with matching
settings, typed catalog entries and presets. Existing `stars` remains the
twinkling effect; `starfield` is perspective flight. All advance one simulation
tick per update, so choose `updates_per_second` explicitly. See the
[creative effects guide](source/creative_effects.rst) for units and resize rules.

The additive `SpriteAsset`, `SpriteClip`, `Sprite`, `ObjectGroup`, `draw_line`,
`draw_rect`, and `draw_ellipse` APIs require no migration. See the
[objects guide](source/objects.rst) for their lifecycle and coordinate contracts.
Assets/clips are shareable values; live sprites and group children have one owner.
An ObjectGroup stays endless even when its children finish and applies membership
commands at startup/update boundaries. Input remains explicitly routed by Player.

`Tile`, `TileMap`, and `Camera2D` are also additive. Maps are immutable data, not
Animations. Wrap their draw method in application drawing code; pass input
handlers to Player explicitly. Coordinates, camera viewports and collision
rectangles use integer cells. Movement sweeps X then Y and treats map boundaries
as solid. See the [top-down guide](source/topdown.rst) for precise contracts.

`AnimationControl` and `ActionQueue` are additive. Choose fixed or continuous
timing explicitly; a paused control sends no child updates. Manual steps are
queued and coalesce until the next parent update. Fixed scheduling shares the
existing Scene catch-up/remainder policy. The top-down demo's queue implementation
now uses ActionQueue with the same capacity and consumption rules. See the
[controls guide](source/controls.rst).

`TextInput`, `Checkbox`, `Button`, and `FocusStack` are additive. Editable controls
own their `.focus` targets; register them in FocusGroup but do not also attach
them to Panel. FocusTarget's optional handler returns EventResult and runs after
its bindings. Existing bindings-only targets are unchanged. FocusStack borrows
groups and does not own modal animations. See the [forms guide](source/forms.rst).

## Reliability corrections

- `Buffer.shift(n)` now follows its documented direction and matches
  `shift_line`: positive rotates right, negative rotates left. Both wrap amounts
  modulo the row width. Code that relied on the former leftward positive `shift`
  should negate its argument. Rain's internal caller is adjusted to preserve wind
  direction.
- `Line.update_points` now takes the same terminal-cell coordinates as the
  constructor. Callers that manually supplied doubled coordinates should stop
  doing so. Stored points returned by `get_points` remain doubled subcell values.
- `TwinkleEffect` copies supplied character lists. `set_twinkle_chars` now raises
  TypeError/ValueError for invalid replacements, leaving the old field and random
  stream intact, instead of silently accepting or ignoring invalid input.
- Terminal write/flush failures propagate through Player after cleanup. A failed
  FramePresenter invalidates its diff baseline so an explicit retry fully repaints.
  Unix resume no longer invokes a removed renderer method: terminal restoration
  and full repaint are requested between frames. No animation restart occurs.
- AnimationSequence propagates parent and timeline visibility to descendants.
  Hidden children and blank gaps cannot receive focused bindings; hiding does not
  pause the timeline. Replacement children inherit visibility before startup.
- Browser snippets construct edited settings using the registered settings class.
  Application-defined effects must be registered by application code first; no
  automatic imports or registration are inferred from saved data.
- Voronoi owner indices support accepted counts beyond 128; wholly offscreen line
  segments no longer prevent subsequent visible segments from drawing.

Existing ownership, seconds/tick conventions, finite completion, and explicit
input routing remain in effect. Physical terminal suspend/resume and hardware
audio support require separate native verification.
