Tweening, themes, and explicit caches
=======================================

Tween callbacks
-----------------

``Tween(setter, start, end, duration=...)`` interpolates a scalar over simulation
seconds. Easing choices are linear, ease_in, ease_out and ease_in_out. ``reverse``
returns to the starting value; ``repeat`` loops. Large time jumps use bounded work.
The setter runs at start and update, never draw. Targets are borrowed: only their
normal owning Scene/Panel closes them. The tween itself is single-use after close.

.. code-block:: python

   from bruhanimate import Label, Panel, Scene, Tween, play

   panel = Panel(Label("Moving"), size=(12, 3))
   motion = Tween(lambda x: panel.move_to((x, 2)), 0, 20,
                  duration=2, easing="ease_in_out", reverse=True, repeat=True)
   play(Scene(motion, panel), duration=5)

Put a tween before its target in Scene when the target's update reads the changed
value. Setters can round integers, interpolate tuples/RGB values, or call an effect's
supported setters. Editing an effect's old settings object does not reconfigure it.
A nonrepeating Tween exposes finite completion; repeated tweens remain unfinished.
Tween does not poll input. Compose finite/endless children according to Scene's
normal completion rules.

Semantic themes
-----------------

``get_theme("dark")``, ``"light"`` and ``"high_contrast"`` return immutable palettes.
Roles are normal, muted, accent, success, warning and error. Themes do not change
global settings or mutate an existing scene. Supply their values when constructing
widgets/effects, or use supported setters for runtime changes.

.. code-block:: python

   from bruhanimate import Label, Panel, get_theme, play

   theme = get_theme("high_contrast")
   panel = Panel(Label("Ready", style=theme.style("success")),
                 size=(24, 4), title="Status", **theme.panel_options())
   play(panel, frames=60)
   assert theme.export_style().background == (0, 0, 0)

``theme.palette`` supplies six ANSI indexes to effects accepting palette lists.
``theme.export_style()`` shares default foreground/background using the fixed xterm
RGB mapping. Terminal-specific palette customizations are not read. Explicit ANSI
colors in frames still override the export defaults.

Cache only explicitly controlled content
------------------------------------------

``CachedAnimation(child)`` owns and starts/closes its child, including on partial
startup failure. It caches drawing, still forwards every update, and never changes
the child's update rate. Call ``invalidate()`` after any visible change; resize also
invalidates. Ordinary Scene children remain uncached. None cells stay transparent
and cached cells do not share mutable objects with presented buffers.

.. code-block:: python

   from bruhanimate import Buffer, CachedAnimation, Label

   cached = CachedAnimation(Label("Static legend"))
   cached.start()
   try:
       cached.draw(Buffer(3, 24))
       cached.draw(Buffer(3, 24))  # child draw is reused
       cached.invalidate()
       cached.draw(Buffer(3, 24))  # child draws again
   finally:
       cached.close()

The cache uses one extra viewport-sized Buffer. It avoids repeated child drawing,
not composition or changed-cell scanning. Use :doc:`performance` benchmarks to
evaluate the tradeoff for your scene. Input routing remains explicit; completion
and visibility follow the child.

API
-----

.. automodule:: bruhanimate.tween
   :members:

.. automodule:: bruhanimate.themes
   :members:

.. automodule:: bruhanimate.cache
   :members:
