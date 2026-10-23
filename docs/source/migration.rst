Migrating to 1.0
================

This is a breaking API release without compatibility adapters. All built-in
effects and packaged demos use start / update(dt) / draw(buffer) / close.

.. code-block:: python

   from bruhanimate import play
   play("snow", frames=120, fps=20, updates_per_second=20)

Replace frame_time with FPS and use None for unlimited frames. Custom effects
implement update(dt) instead of render_frame(frame_number), retaining a private
simulation counter if necessary. BaseEffect draws the current persistent raster.
Pass a custom factory directly instead of replacing a dummy renderer's effect.

The bruhrenderer package and its root exports are removed:

* EffectRenderer/BaseRenderer loops become play or Player.
* CenterRenderer becomes Scene(background, ImageEffect(rows)).
* PanRenderer becomes ImageEffect with explicit position and velocity in cells/second.
* BackgroundColorRenderer becomes a styled drawing callback in a Scene.
* TerminalRenderer becomes TerminalEffect with explicit event handling.
* FireworkEffect.set_second_effect becomes an independent lower layer.
* FocusRenderer's character assembly has no built-in replacement yet.

Panning clips rather than preserving old looping semantics. Water's unfinished
placeholder is removed. Scene does not infer collision geometry from visible
layers; configure effect collision inputs explicitly. None cells reveal lower
layers, and Layer(transparent=True) also makes plain spaces transparent.

Audio starts at start(), and Player/Scene own cleanup. play owns terminal
restoration; Player borrows its Screen. Shutdown is prompt-free. All demos expose
``run(*, frames=None, fps=...)`` and no longer take a Screen argument. Multi-phase
demos cycle configurations with one player; quit exits the whole showcase.

See the `complete migration guide
<https://github.com/FNBBDevs/bruhanimate/blob/main/docs/MIGRATING_1.0.md>`_
for examples, ownership rules, and included reliability fixes.
