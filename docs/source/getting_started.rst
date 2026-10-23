Getting started
===============

bruhanimate turns Python state into terminal animation. Start with an effect,
compose a scene, or feed solver snapshots into the same player.

Install
-------

Use Python 3.13 or newer. Once a 1.x release is available on PyPI:

.. code-block:: sh

   python -m pip install "bruhanimate>=1,<2"

For optional audio capture dependencies, install ``bruhanimate[audio]>=1,<2``.
The base package and non-audio effects do not require audio capture packages.

To try unreleased code from the repository instead:

.. code-block:: sh

   git clone https://github.com/ethanlchristensen/bruh.animate.git
   cd bruh.animate
   git switch dev
   uv sync --locked --python 3.13

Install the uv version pinned in pyproject.toml (currently 0.13.4). This creates
an editable installation of the checkout. Prefix Python commands below with
``uv run --locked`` when using this source environment; activation is unnecessary.

Your first animation
--------------------

Save this complete example as animation.py:

.. code-block:: python

   from bruhanimate import play

   play("snow", preset="light", fps=60, updates_per_second=30)

Run it in a terminal:

.. code-block:: sh

   python animation.py

Press q, Escape, or Ctrl+C to quit. The player restores the terminal on exit.
This example presents up to 60 frames per second while updating the simulation
30 times per second. ``frames=120`` would limit presentations to 120 frames.

Use a preset or explicit settings
---------------------------------

Named presets are convenient starting points. For more control, pass a settings
object; explicit settings take precedence over a preset:

.. code-block:: python

   from bruhanimate import SnowSettings, play

   play(
       "snow",
       settings=SnowSettings(intensity=0.02, wind=0.2),
       fps=60,
       updates_per_second=30,
   )

Use ``effect_registry.names()`` to list effect names and
``effect_registry.presets("snow")`` to discover that effect's presets.

Try the demos
-------------

.. code-block:: sh

   python -m bruhanimate.demos.fire_demo
   python -m bruhanimate.demos.shared_player_demo
   python -m bruhanimate.demos.grid_demo

Run one command at a time. The grid demo includes a complete BFS solver and an
animated background. Space pauses, n/right arrow steps, +/- changes speed, and q
quits. The completed solution remains visible until quit.

Where to go next
----------------

* :doc:`concepts`: how state, drawing, the player, and scenes fit together.
* :doc:`player`: custom effects, timing, composition, and resource ownership.
* :doc:`playback` and :doc:`grid`: solver snapshots and board drawing.
* :doc:`migration`: moving an existing 0.2.x animation to 1.x.
* :doc:`contributing` and :doc:`releasing`: repository checks and package publishing.
