Release 1.6.0
=============

Version 1.6.0 adds sprite and top-down game foundations, editable TUI controls,
modal focus, playback controls and three new procedural effects. It also repairs
terminal output/resume handling, sequence focus, effect settings isolation,
Voronoi indices and line drawing.

New procedural effects
----------------------------------------

* warp_demo composes an original animated spaceship over the warp starfield,
  retaining flight/engine phase across resize and using compact art in small views.
* Flow adds curling particle trails with neon/ocean/ember presets.
* Growth adds bounded branching coral/forest/electric generations.
* Starfield adds perspective drift/warp/spiral flight with depth and streaks.
  All three include validated settings, seeds, browser discovery, typed presets,
  standalone demos and state-preserving resize. See :doc:`creative_effects`.

Editable forms and modal focus
----------------------------------------

* TextInput, Checkbox and Button own intrinsic focus targets and preserve edit
  state across resize. FocusTarget supports a typed fallback event handler.
* FocusStack isolates nested modal input and restores eligible prior focus.
  settings_demo exercises Apply/Cancel, draft editing and background shortcut
  isolation. See :doc:`forms` for input, lifecycle and visibility contracts.

Timing and actions
------------------

* AnimationControl adds explicit fixed/continuous timing, pause/resume, queued
  single-step and time scaling. Fixed mode shares Scene's bounded catch-up policy.
* ActionQueue provides bounded FIFO commands and KeyBinding callbacks for explicit
  update-time consumption. The top-down demo uses it, and controls_demo combines
  controlled fixed-tick snow with continuous sprite motion. See :doc:`controls`.

Object foundations
------------------

* Tile and TileMap provide shareable cell maps, separate visual/collision flags,
  clipped drawing, rectangle queries and axis-separated swept grid movement.
* Camera2D provides bounded cell-space translation and dead-zone follow.
  The playable topdown_demo adds queued movement, collectibles and pause/reset;
  see :doc:`topdown` for its input and timing contracts.

* Immutable SpriteAsset and SpriteClip values can be shared between independent
  Sprite instances, with cell-based position, velocity, anchors, flips and clipping.
* ObjectGroup owns named children with queued add/remove/reorder operations,
  explicit cleanup, resize/visibility propagation and isolated drawing.
* draw_line, draw_rect and draw_ellipse paint styled single-cell glyphs with
  viewport-bounded work. The objects_demo combines sprites and temporary sparks.

See :doc:`objects` for executable examples, ownership, units and completion.
These APIs are additive; existing Scene composition remains unchanged.

Reliability corrections
-----------------------

* Terminal write/flush failures propagate after cleanup. Unix resume queues a
  full repaint without restarting animation state; see :doc:`player`.
* Sequence gaps and hidden ancestors disable descendant focus, including across
  replacement/repeat boundaries; see :doc:`sequencing`.
* Buffer horizontal rotations now consistently use positive-right and
  negative-left amounts, wrapping modulo width. Existing callers that relied on
  the reversed ``shift`` implementation should negate their arguments.
* Line endpoint updates now use constructor cell units. ``get_points`` retains
  doubled subcell output. Offscreen segments are rejected individually.
* Twinkle copies character lists and validates replacements before changing its
  field. Voronoi no longer overflows its owner indices above 128 sites.
* Edited browser snippets use the registered settings type. Application-defined
  effects require application registration first; see :doc:`workbench`.

See the `migration notes
<https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/MIGRATING_1.6.md>`_
for caller adjustments.
