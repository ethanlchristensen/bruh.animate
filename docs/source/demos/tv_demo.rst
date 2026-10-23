TV demo
=======

A retro TV plays colorful plasma while snow falls behind its cabinet. Run it
directly in your terminal, including Windows Terminal; press q to quit:

.. code-block:: shell

   python -m bruhanimate.demos.tv_demo

From Python, type ``tv_demo.`` for the typed ``run`` and ``build_scene`` helpers:

.. code-block:: python

   from bruhanimate import tv_demo

   tv_demo.run(frames=180, fps=60)

The scene paints five layers, in order:

1. Snow across the terminal, updating 15 times per second.
2. An opaque ASCII cabinet, bezel, tuning knobs, antenna, and feet.
3. Plasma updating 30 times per second, clipped to the TV screen rectangle.
4. A two-second channel badge clipped to the same screen.
5. A title and quit hint outside the cabinet.

Player presents at 60 FPS. Each simulation owns a separate full-terminal buffer;
the region clips painting without translating or resizing the simulation. Snow
continues behind the cabinet, whose painted spaces hide it. When the badge
expires, the current plasma shows through. ``on_complete="hold"`` keeps both
effects running after that finite overlay completes.

Edit the ``SnowSettings`` and ``PlasmaSettings`` in ``build_scene`` to change the
look; editor completion lists their options. Layout is computed at construction,
fits comfortably at 80 columns by 24 rows, and clips safely in tiny windows.
Live resize reconstruction is not implemented. No external player is required.
See :doc:`../composition` for clipping, timing, and ownership contracts.

.. automodule:: bruhanimate.demos.tv_demo
   :members:
