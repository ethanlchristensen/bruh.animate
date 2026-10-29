Warp spaceship demo
===================

An original ASCII spaceship flies through the ``starfield`` effect's ``warp``
preset. Engine flames animate while the ship gently drifts across the view.
Opaque hull cells cover background stars; cells outside the silhouette remain
transparent. No image assets or additional dependencies are needed.

.. code-block:: bash

   uv run --locked python -m bruhanimate.demos.warp_demo

Press q, Escape or Ctrl+C to exit. The demo flies automatically. Resize preserves
star positions, flight phase and engine animation; small terminals select a
compact ship or a single-cell marker. The HUD is hidden when space is limited.

The scene owns both the background and ship. Starfield advances at 30 ticks/sec;
ship motion and sprite clips use elapsed seconds. Player owns input, pacing and
terminal cleanup. ``run(frames=120)`` bounds playback; ``build_scene`` can also
be passed to capture. All drawing is independent of simulation updates.

.. automodule:: bruhanimate.demos.warp_demo
   :members: build_scene, run
