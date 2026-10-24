Paths, pulses, and ripples
==========================

``PathEffect``, ``PulseEffect``, and ``RippleEffect`` are transparent animations
for highlighting a board. They use the same board coordinates and spacing as
``GridViewport``. Supply the board ``size=(columns, rows)``; ``x=None, y=None``
centers the board in the current buffer on every draw, including after resize.
Explicit coordinates anchor it instead. Layer regions and masks provide clipping.

.. code-block:: python

   from bruhanimate import PathEffect, PulseEffect, RippleEffect, Scene, capture

   scene = Scene(
       PathEffect([(0, 1), (1, 1), (2, 1), (3, 1)], size=(5, 3),
                  mode="trace", duration=2, hold_duration=1),
       PulseEffect((0, 1), size=(5, 3), colors=(238, 250, 255), duration=1),
       RippleEffect((3, 1), size=(5, 3), metric="manhattan", radius=2, duration=2),
   )
   capture(scene, on_frame=lambda frame: None, width=20, height=6, frames=4)

Options and timing
------------------

* ``PathMode`` completes ``"pulse"`` (moving marker with ``trail`` previous
  cells) and ``"trace"`` (all visited cells). ``points`` is copied at construction;
  entries receive equal time intervals. Points are not interpolated and no path
  finding is performed. Include every desired cell; repeated points create pauses.
* ``PulseEffect.colors`` is a nonempty sequence of ANSI palette indices 0..255.
  ``cycles`` controls triangular foreground brightness cycles during ``duration``.
  This is a color pulse, not opacity blending. ``glyph`` defaults to ``"*"``.
* ``RippleMetric`` completes ``"euclidean"`` (circle), ``"manhattan"`` (diamond),
  and ``"chebyshev"`` (square). ``radius`` and ``thickness`` are measured in board
  cells, independent of display spacing. Only visible cells are visited when drawing.

``duration`` is positive seconds; ``hold_duration`` freezes the final state before
it disappears. An empty path is finished immediately. Nonrepeating accents report
``finished=True`` and draw nothing after duration plus hold. With ``repeat=True``,
``repeat_delay`` is the blank gap before the next cycle; finished stays false.
Large updates skip whole cycles without replaying them. Drawing never advances time.
These helpers acquire no resources; a Scene or Player owns their lifecycle.
Use a fresh instance for each owner. For sequential highlights, use
:doc:`sequencing` and factories rather than sharing animations.

Run the complete :doc:`demos/routing_demo` to see a source pulse, traced route,
moving marker, and arrival ripple over an independently animated background.

API
---

.. automodule:: bruhanimate.motion
   :members: PathEffect, PulseEffect, RippleEffect, PathMode, RippleMetric
