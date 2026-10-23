Moving windows demo
===================

Four framed windows bounce around the terminal, each carrying a different
animation: plasma, fire, snow, and Matrix rain. Run it natively, including in
Windows Terminal; press q to quit:

.. code-block:: shell

   python -m bruhanimate.demos.windows_demo

From Python, the typed ``run`` entry point also accepts a frame limit and FPS:

.. code-block:: python

   from bruhanimate import windows_demo

   windows_demo.run(frames=180, fps=60)

How the windows compose
-----------------------

Each effect owns a window-sized buffer. A public ``Panel`` owns and paces that
effect, draws it into a separate local canvas, then copies its cells into the
destination at the moving window's position. This translates the whole
simulation, including the fire's source at the bottom of its own window.
``Layer.region`` remains a destination clip; it does not translate content.

Titles and borders move with their contents. Plain spaces inside each window
are opaque. Windows paint in a fixed order, from plasma at the back to Matrix at
the front, and pass over one another without collision physics. Every frame
repaints the desktop and current windows, revealing underlying content as a
window moves away, without modifying older presented frames.

Motion advances in ``update(dt)`` using columns/second and rows/second, with
reflected positions at the desktop edges. Plasma and fire update at 30/s, snow
at 15/s, and Matrix at 20/s. The shared Player supplies 60 simulation updates
per second and presents at 60 FPS by default. Draw never advances a simulation.

The outer Scene owns the panels; each panel owns its effect through a local
Scene. Cleanup follows that chain, including failed startup. Instances
and mutable buffers are never shared between owners. No separate loops, threads,
or terminal handles are created. The scene runs until q or the frame limit.

Customization
-------------

Edit ``build_scene`` to change the typed ``PlasmaSettings``, ``FireSettings``,
``SnowSettings``, or ``MatrixSettings``, window velocities, border colors, or
panel update rates. ``Panel`` exposes these named, typed options directly;
type ``Panel(`` in your editor for completion. Content size excludes its border.
The faster velocities (18, -15, 12, and -9 columns/second) are retained.
See :doc:`../panels` to build your own composition with the public API.

An 80-column by 24-row terminal shows all four windows initially. Layout uses
the initial dimensions; smaller terminals clip safely, and windows too large
for an axis stay anchored on that axis. The header and footer remain outside
the windows' clipping region. Live terminal resize reconstruction is not
implemented. See :doc:`../composition` for the shared API contracts.

.. automodule:: bruhanimate.demos.windows_demo
   :members:
