Core concepts
=============

An animation has two jobs: advance its state and draw that state. The player
handles when those jobs run, keyboard input, terminal output, and cleanup.
Scenes combine animations; Playback connects a state generator to drawing.

Choose a starting point
-----------------------

.. list-table:: Building blocks
   :header-rows: 1
   :widths: 25 75

   * - Building block
     - Responsibility
   * - ``play`` / ``Player``
     - Run the clock, input, updates, and presentation. play owns a terminal;
       Player borrows an existing Screen.
   * - ``Animation``
     - The start / update / draw / close interface accepted by the player.
   * - ``CallbackEffect``
     - Supply drawing and optional update functions for a small custom animation.
   * - ``BaseEffect``
     - Keep a persistent private raster; implement update and inherit raster drawing.
   * - ``Buffer``
     - A rectangular grid of terminal cells, with clipped drawing operations.
   * - ``Scene`` / ``Layer``
     - Paint independent animations in order, with explicit space transparency.
   * - ``ImageEffect``
     - Place or move text and ASCII art within a scene.
   * - ``Playback`` / ``draw_grid``
     - Consume solver snapshots at a chosen rate and draw logical board coordinates.

1. Update state; draw its current value
---------------------------------------

Keep simulation in ``update(dt)``. Treat state as read-only while drawing:

.. code-block:: python

   from bruhanimate import CallbackEffect, play

   state = {"x": 0.0}

   def update(dt):
       state["x"] += 12 * dt  # columns per second

   def draw(buffer):
       x = int(state["x"]) % buffer.width()
       buffer.put_char(x, buffer.height() // 2, "*")

   play(CallbackEffect(draw, update=update), fps=60, updates_per_second=30)

``dt`` is seconds. The star moves 12 columns per simulated second even if you
change the drawing FPS. Repeated draws of the same state must not move the star,
read a solver's next result, or acquire resources.

Built-in simulations are discrete: most advance one step per update and their
existing probabilities/speed settings use ticks. Give them an explicit update
rate when their speed should remain independent of presentation FPS.

2. Draw into cells, not directly to the terminal
------------------------------------------------

The player supplies a fresh drawing buffer for each presentation. Use methods
such as ``put_char(x, y, value)``, ``put_at(x, y, text)``, and
``put_at_center(row, text)``. Coordinates start at the top-left; x is the column
and y is the row. ``Buffer(height, width)`` takes dimensions in that order.

The presenter compares completed frames and writes changed cells in a batch.
Do not print or emit cursor escapes while the player owns terminal presentation,
retain the target drawing buffer, or mutate a previously displayed frame.
Use single-cell characters; wide/combining glyphs are not supported by the grid
helpers. ``ImageEffect`` accepts text or ASCII rows, not raster image files.

BaseEffect is useful when the simulation itself needs a persistent raster.
Give it a private buffer and implement update; its default draw copies the
current raster into the supplied drawing target.

3. Compose independent animations
---------------------------------

A factory receives a screen-sized buffer when playback opens. Return the content
you want to run:

.. code-block:: python

   from bruhanimate import ImageEffect, Scene, effect_registry, play

   def build(buffer):
       snow = effect_registry.create("snow", buffer, " ", preset="light")
       title = ImageEffect("Advent of Code")
       return Scene(snow, title)

   play(effect_factory=build, fps=60, updates_per_second=30)

Children paint from back to front. Each draws into an isolated scratch buffer
before composition. ``None`` cells reveal the layer below. Plain spaces paint;
wrap an animation with ``Layer(animation, transparent=True)`` to make plain
spaces transparent too. Colored background spaces still paint.

ImageEffect centers by default. Supply x/y for an explicit position, or velocity
in columns/second and rows/second for movement. With multiple raster-based built-in
effects, allocate a distinct private Buffer for each; do not share their mutable
simulation raster. Scene currently gives all children the same update rate.

4. Let the solver produce snapshots
-----------------------------------

For Advent of Code, keep puzzle rules in a normal generator. Yield an independent
snapshot whenever the visual state changes. Playback decides when to request
another snapshot, and the draw callback decides how it looks:

.. code-block:: python

   from bruhanimate import Playback, draw_grid, play

   board = ("S...", ".##.", "...E")

   def states():
       yield from ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2))

   def draw(position, buffer):
       grid = draw_grid(buffer, board, spacing=(2, 1))
       grid.put(*position, "@")

   playback = Playback(states(), draw, steps_per_second=5)
   play(
       playback,
       fps=60,
       updates_per_second=30,
       event_handler=playback.handle_event,
       on_complete="hold",
   )

The example generator is a small fixed path; replace it with your solver. A
snapshot can instead be a frozen dataclass containing beams, visited cells,
counters, or a final path. Drawing must read the snapshot without changing it.
If a producer reuses mutable state, supply ``copy_state=deepcopy`` or yield
independent values yourself.

There are three separate rates:

.. list-table:: Timing controls
   :header-rows: 1

   * - Setting
     - Meaning
   * - ``fps=60``
     - Present up to 60 frames per second.
   * - ``updates_per_second=30``
     - Update all animation children 30 times per second.
   * - ``steps_per_second=5``
     - Ask the solver for five snapshots per simulated second.

Pass the Playback event handler explicitly to enable Space/pause, n/right-arrow
step, +/- speed, and q/quit. Pausing a Playback does not pause a scene's background.
``on_complete="hold"`` keeps its final state visible; ``"exit"`` closes after
presenting completed content. An endless background does not prevent a scene's
finite Playback child from completing.

Playback retains one snapshot without prefetch or rewind and closes its owned
iterator on exhaustion or early quit. Solver calls run synchronously: keep work
between yields bounded and sample large searches rather than storing every state.
See :doc:`playback` for completion and source-ownership details.

5. Give resources one owner
---------------------------

.. list-table:: Animation lifecycle
   :header-rows: 1

   * - Method
     - Job
   * - ``start()``
     - Acquire resources when playback starts. Constructors and imports stay inert.
   * - ``update(dt)``
     - Advance the model; never present it directly.
   * - ``draw(buffer)``
     - Paint the model; do not advance it.
   * - ``close()``
     - Release resources safely, including after partial startup or repeated calls.

By default, the player owns its animation and registers cleanup before startup.
A Scene owns its children and closes them in reverse startup order. Create fresh
instances to replay or change membership; do not share one animation instance
between owners. Immutable model data can be shared.

``play`` opens and restores a Screen for you. ``Player`` borrows a Screen for
embedding or tests. Resizing currently ends playback with ScreenResizedError
after cleanup; automatic reflow, rewind, and image/video export are future work.
Seeded headless frames and terminal recordings are available through :doc:`capture`.

Next, use :doc:`player` for the detailed contracts, :doc:`grid` for viewport
coordinates and styling, or :doc:`demos/index` for complete examples.
