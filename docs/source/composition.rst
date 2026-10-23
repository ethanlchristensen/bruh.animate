Panels, layer clocks, and temporary overlays
============================================

Scene composes animations in paint order. Each Layer can clip its output to a
rectangle and choose an independent simulation rate. TimedOverlay makes a child
visible for a limited time, then releases it and reveals the current lower layers.
These features use the existing Player and work with native terminal playback;
no additional application or dependency is required.

.. code-block:: python

   from bruhanimate import ImageEffect, Layer, Scene, TimedOverlay, effect_registry, play

   def build(buffer):
       panel = (1, 2, max(0, buffer.width() - 2), max(0, buffer.height() - 4))
       snow = effect_registry.create("snow", buffer, " ", preset="moderate", seed=42)
       return Scene(
           ImageEffect("Snow panel", x=1, y=0),
           Layer(snow, region=panel, updates_per_second=15),
           Layer(TimedOverlay(ImageEffect("This message disappears"), duration=2),
                 region=panel),
       )

   play(effect_factory=build, fps=60, updates_per_second=60,
        duration=5, on_complete="hold")

Type ``Layer(`` in an editor to discover ``region``, ``updates_per_second``, and
``max_catch_up``. ``TimedOverlay`` exposes typed ``duration`` and ``delay`` fields
in its constructor. Configure layers and overlays before starting playback.

Clipped regions
---------------

``region=(x, y, width, height)`` uses scene/destination coordinates. Width and
height are non-negative integers; zero means nothing is painted. Origins may be
negative, and rectangles are intersected with the destination Buffer. ``None``
uses the whole destination. Fully clipped layers still start and update, but
their draw calls can be skipped.

Clipping does not move the child or change its drawing dimensions. Children
receive a full-scene scratch Buffer, so a built-in effect's private raster still
matches that Buffer. An ImageEffect at ``x=0`` is not moved to a region's left
edge. Set its position explicitly, or use GridViewport's region to lay out a
board within a panel. Nested layer clips intersect. This is a visual boundary;
it does not create simulation collision walls.

``None`` cells remain transparent. Plain spaces paint unless
``transparent=True``; ANSI-colored spaces still paint. Each presentation draws
the latest state into isolated scratch buffers, then copies only visible cells.
Keep separate private Buffers for separate raster-based effects.

Independent update rates
-------------------------

With ``updates_per_second=None``, a layer receives every Scene update unchanged.
A configured positive, finite rate accumulates Scene ``dt`` and delivers fixed
``1 / rate`` ticks. The first tick waits for one complete interval; construction,
startup, and drawing do not consume ticks. Drawing still happens every presentation,
including between ticks. Each Scene instance owns its layer accumulators.

For example, ``Layer(snow, updates_per_second=15)`` runs snow at 15 simulation
ticks per supplied second while Player presents at 60 FPS. Player's scene update
rate controls scheduling granularity. If a layer needs more ticks than its parent
delivers, Scene performs multiple ticks during one update; it does not create
another playback loop or present intermediate frames.

``max_catch_up=5`` limits work per layer per Scene update. Reaching that cap drops
remaining accumulated time, including the fractional remainder, to prevent a
long stall from causing unbounded work. Raise it deliberately when a large ratio
of child/parent rates requires more ticks. This bound also applies during headless
capture. Layer time follows delivered simulation time, not wall time discarded by
Player's own catch-up policy. Rates cannot be edited on a frozen Layer.

Playback already has ``steps_per_second`` for solver progression. Usually leave
its Layer rate unset so pause/step commands are processed on the next Scene
update. Rate-limiting its Layer also limits when those controls take effect.
Route input explicitly with ``event_handler=playback.handle_event``. Pausing that
solver does not pause snow, other layers, or an independently updated overlay.

Temporary overlays and ownership
---------------------------------

``TimedOverlay(child, duration=2, delay=1)`` is visible in the half-open interval
``[1, 3)`` of supplied simulation seconds. It starts its child when the delay
elapses, forwards only the active portion of an update, and closes the child on
expiry. If one update skips an entire delayed window, the child is never started.
``duration=0`` never starts it. Negative/non-finite times are rejected.

Expiry happens in update, so the next draw paints nothing and reveals the latest
lower layers. The wrapper never erases or modifies a previously presented frame.
A child finishing early does not shorten the visibility window. Delayed startup
failures close the failing child; owner cleanup closes active children once.
Closing before startup is safe. TimedOverlay is single-use, like Playback.
Do not share its child with another owner or add that child separately to Scene.

An overlay reports ``finished=True`` on expiry and participates in Scene's finite
completion. A scene with an endless background and one overlay therefore finishes
when that overlay expires. Use ``on_complete="hold"`` to keep the background
playing until another limit or quit. A scene with a finite solver waits for both
solver completion and overlay expiry. The overlay does not forward input events.

A complete second example
--------------------------

Run the beam demo in your usual terminal, including Windows Terminal:

.. code-block:: shell

   python -m bruhanimate.demos.beam_demo

.. code-block:: python

   from bruhanimate import beam_demo

   beam_demo.run(frames=180, fps=60)

An original 15-by-9 public board sends beams downwards; ``^`` splits a beam
diagonally into the following row and overlapping beams merge. The pure lazy
solver keeps immutable snapshots and does not enumerate branch histories.
Snow updates at 15/s inside the panel, the solver advances at 5 steps/s, and
Player presents at 60 FPS. A one-second introductory message disappears while
the board continues evolving underneath. The status display remains outside the
snow panel. Space pauses, n/right steps, +/- changes solver speed, and q quits.

The demo uses ASCII geometry with ANSI colors; smaller windows clip the board.
The final board stays visible until quit or the frame limit. This complements the
existing BFS grid demo and keeps all puzzle rules in application/demo code.
General masks, reusable path pulses/ripples, and resize reconstruction remain
future work.

TV composition example
----------------------

For a scene without a solver, run ``python -m bruhanimate.demos.tv_demo``.
Plasma plays inside an opaque retro TV while snow falls behind it. A clipped
channel badge expires after two seconds. The effects use separate buffers and
update rates; the shared Player presents at 60 FPS. See :doc:`demos/tv_demo` for
the full layer order and customization points.

Moving windows example
----------------------

Run ``python -m bruhanimate.demos.windows_demo`` for four bouncing windows,
each with its own effect, rate, and local buffer. Public :doc:`panels` translate
the pixels and border together; panel bounds protect the header and footer. See :doc:`demos/windows_demo` for ownership and customization.

Compatibility
-------------

Existing ``Layer(animation)`` and ``Layer(animation, transparent=True)`` retain
their behavior. New options are keyword-only. Scene now rejects negative or
non-finite ``dt``; layers reject malformed regions, rates, and catch-up bounds
before starting content. ``transparent`` must be a bool. See :doc:`player` for
the Scene/Layer/TimedOverlay API reference.
