Image effects showcase
==============================

Run ``python -m bruhanimate.demos.image_demo`` for six independent panels:

* Glitch: fly-in lettering with flickering symbols.
* Focus: scattered characters assemble into ``bruh``.
* Dissolve: characters appear in seeded random order.
* Wipe: a straight edge reveals the text, then retracts.
* AnimationSequence: a playlist using fresh transition factories.
* ImageMask: plasma is visible only through the shape of the lettering.

The transition panels animate in, hold their final image for three seconds,
animate back out in reverse, and hide for one second before repeating. Their
plasma backgrounds keep running. ``reverse=True`` retraces the same seeded
frames, with each leg taking the original transition duration. Layer styling
keeps bright text over the current plasma background color without custom ANSI
handling. Each panel owns its own plasma instance and transition.

An 80x40 terminal gives the panels room to show their small pyfiglet text. Column,
Row, and fit-enabled Panel containers reflow on resize; tiny viewports clip safely
without resetting transitions. Each plasma updates at 30 Hz while presentation
and transition updates run at 60 Hz. Press q to quit.

.. code-block:: python

   from bruhanimate import image_demo

   image_demo.run(frames=600, fps=60)

``build_scene(buffer)`` is a complete example composed from public APIs.
See :doc:`../images` for constructors, typed options, masks, and lifecycle rules.

.. automodule:: bruhanimate.demos.image_demo
   :members:
