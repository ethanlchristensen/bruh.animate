Bruhanimate 1.0
===============

Terminal animations use one Player for built-in effects, custom drawings, and
composed scenes. This major release removes the old renderer classes.

.. code-block:: python

   from bruhanimate import play

   play("snow", preset="light", fps=60, updates_per_second=30)

q, Escape, and Ctrl+C exit and restore the terminal. See the player guide for
ownership, input, timing, and custom-effect examples, and the migration guide for
removed APIs and intentional behavior changes.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   player
   playback
   grid
   migration
   contributing
   bruheffect/index
   bruhutil/index
   demos/index
