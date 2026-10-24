TV demo
=======

The original v0.2 ``computer`` artwork plays colorful plasma inside its angled
monitor, with snow falling behind the computer and keyboard. The existing
``tv_demo`` entry point remains the same; press q to quit:

.. code-block:: shell

   python -m bruhanimate.demos.tv_demo

From Python, type ``tv_demo.`` for the typed ``run`` and ``build_scene`` helpers:

.. code-block:: python

   from bruhanimate import tv_demo

   tv_demo.run(frames=180, fps=60)

The scene paints six layers, in order:

1. Snow across the terminal, updating 15 times per second.
2. The bundled ``get_image("computer")`` artwork, including its keyboard.
3. Plasma updating 30 times per second, masked to the angled monitor opening.
4. Pyfiglet ``bruh`` lettering in the ``small`` font. After two seconds, it cycles
   through Glitch (fly-in), Focus (assembly), Dissolve (random reveal), and Wipe.
   Each entrance holds its completed text for three seconds, retraces the effect
   in reverse, then leaves a one-second gap before the next entrance. Plasma
   keeps running throughout.
5. A two-second channel badge inside the monitor.
6. A title, current transition name, and quit hint at the viewport edges.

The monitor's shape uses per-row spans in artwork coordinates, rather than a
rectangular clip that would overwrite its sloping bezel. The bundled artwork
keeps its original shape with an extra space in the right bezel corrected.
Spaces inside each silhouette row paint opaquely, hiding snow
inside the computer; leading/trailing padding leaves the background visible.

Player presents at 60 FPS. Both simulations own separate full-viewport buffers.
When the badge expires, lettering starts flying in. Its blank spaces remain
transparent, and each visible glyph retains the current plasma background color.
The four public image effects supply the animation. ``AnimationSequence`` owns
one active transition, closes it before switching, and creates fresh transitions
on each cycle. ``Layer(mask=...)`` clips plasma and lettering to the monitor;
``style=TextStyle(foreground=231, bold=True), preserve_background=True`` composes
the text over current plasma colors. No custom ANSI rewriting or direct access
to the background raster is needed. ``on_complete="hold"`` keeps playback live.
Only text transitions switch; neither plasma nor the startup badge restarts.
The sequence enables ``reverse=True`` on each effect, with a three-second hold
and one-second gap. Glitch launches at 18 glyphs/sec with 0.65-second flights;
Focus, Dissolve, and Wipe take 2.5 seconds per leg. The exit exactly retraces the entrance,
including glitch symbols, scatter paths, and dissolve ordering.

An 80-column by 34-row terminal shows the whole computer. Resize recenters the
original-size artwork without restarting simulations, layer clocks, or the
badge or text reveal. Shorter terminals prioritize the monitor and clip the keyboard; narrow
terminals clip horizontally. Header/footer rows remain reserved. Live resizing
is enabled by default; pass ``on_resize="raise"`` to stop on resize instead.

Edit ``SnowSettings`` and ``PlasmaSettings`` in ``build_scene`` to change the look.
The monitor mask and artwork placement live in the demo, using the normal Scene
and Animation contracts. No renderer compatibility layer or external player is
required. See :doc:`../images` for reusable effects, masks, and styling.

.. automodule:: bruhanimate.demos.tv_demo
   :members:
