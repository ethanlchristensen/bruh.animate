bruhanimate
===========

Composable terminal animations for Python
-----------------------------------------

Run a built-in effect, combine layers, or animate snapshots from your own solver.
One player handles timing, input, changed-cell rendering, and terminal cleanup.
Requires Python 3.13 or newer.

.. code-block:: python

   from bruhanimate import play

   play("snow", preset="light", fps=60, updates_per_second=30)

Press q, Escape, or Ctrl+C to quit and restore the terminal.

Start here
----------

* **New to the library?** Follow :doc:`getting_started` to install and run a demo.
* **Building your own animation?** Read :doc:`concepts` for state, drawing, layers,
  and the animation lifecycle before diving into the API.
* **Visualizing Advent of Code?** Use :doc:`playback` and :doc:`grid` to connect a
  snapshot generator to board drawing and interactive playback controls.
* **Upgrading from 0.2.x?** Follow :doc:`migration`; v1 removes the old renderers.
* **Contributing or publishing?** Use :doc:`contributing` and :doc:`releasing`.

.. toctree::
   :maxdepth: 1
   :caption: Learn

   getting_started
   concepts

.. toctree::
   :maxdepth: 2
   :caption: Guides and API

   player
   playback
   grid
   migration
   bruheffect/index
   bruhutil/index
   demos/index

.. toctree::
   :maxdepth: 1
   :caption: Project

   contributing
   releasing
