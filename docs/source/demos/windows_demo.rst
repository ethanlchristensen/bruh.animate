Moving windows demo
===================

Five framed windows bounce around the terminal, each carrying a different
animation: plasma, fire, snow, Matrix rain, and Mirror's centered audio bars.
Play music or a
video and run it natively, including in Windows Terminal; press q to quit:

.. code-block:: shell

   uv run --locked --extra audio python -m bruhanimate.demos.windows_demo

For a pip installation, install ``bruhanimate[audio]`` and run
``python -m bruhanimate.demos.windows_demo``. Capture uses the same optional
backend as the :doc:`audio_demo`. If unavailable, the audio window and footer
show an error while the other four effects keep running.

From Python, the typed ``run`` entry point also accepts a frame limit and FPS:

.. code-block:: python

   from bruhanimate import windows_demo

   windows_demo.run(frames=180, fps=60, audio_mode="mirror")

``audio_mode`` provides editor completion for all seven audio modes. For example,
use ``"mirror"`` for centered bars or ``"glow"`` for reacting pools of color.
Use ``audio_mode=None`` to omit the fifth window entirely and open no audio
device. The rendering benchmarks explicitly retain this four-window workload.

How the windows compose
-----------------------

Each effect owns a window-sized buffer. A public ``Panel`` owns and paces that
effect, draws it into a separate local canvas, then copies its cells into the
destination at the moving window's position. This translates the whole
simulation, including the fire's source at the bottom of its own window.
``Layer.region`` remains a destination clip; it does not translate content.

Titles and borders move with their contents. Plain spaces inside each window
are opaque. Windows paint in a fixed order, from plasma at the back to audio at
the front, and pass over one another without collision physics. Every frame
repaints the desktop and current windows, revealing underlying content as a
window moves away, without modifying older presented frames.

Motion advances in ``update(dt)`` using columns/second and rows/second, with
reflected positions at the desktop edges. Plasma and fire update at 30/s, snow
at 15/s, Matrix at 20/s, and audio at 30/s. The shared Player supplies 60 simulation updates
per second and presents at 60 FPS by default. Draw never advances a simulation.

The outer Scene owns the panels; each panel owns its effect through a local
Scene. Cleanup follows that chain, including failed startup. Instances
and mutable buffers are never shared between owners. Audio starts its capture
worker only when the scene starts and stops it on close; building the scene
opens no device or thread. Player remains the only playback loop and terminal
owner. The scene runs until q or the frame limit.

Customization
-------------

Edit ``build_scene`` to change the typed ``PlasmaSettings``, ``FireSettings``,
``SnowSettings``, ``MatrixSettings``, or ``AudioSettings``, window velocities, border colors, or
panel update rates. ``Panel`` exposes these named, typed options directly;
type ``Panel(`` in your editor for completion. Content size excludes its border.
The original velocities (18, -15, 12, and -9 columns/second) are retained;
the audio window moves at 21 columns/second and -4.2 rows/second.
See :doc:`../panels` to build your own composition with the public API.

Windows occupy 36×11 cells on an 80×24 terminal and grow up to 60×20 cells on
larger terminals (including borders). Larger windows overlap, so front windows
can temporarily hide rear titles and content. Layout uses
the initial dimensions; smaller terminals clip safely, and windows too large
for an axis stay anchored on that axis. The header and footer remain outside
the windows' clipping region. Live terminal resize is enabled by default;
window sizes and bounce bounds retain their initial geometry and clip safely
to the new viewport. See :doc:`../composition` for the shared API contracts.

.. automodule:: bruhanimate.demos.windows_demo
   :members:
