Flow trails, branching growth and star flight
=============================================

Three procedural effects provide curling particle trails, branching shoots,
and perspective star flight. Each is available through the typed catalog,
registry, command line and effect browser, with no additional dependencies.

.. list-table:: Effects and presets
   :header-rows: 1
   :widths: 22 30 48

   * - Effect / settings
     - Presets
     - Appearance
   * - flow / FlowSettings
     - neon, ocean, ember
     - Glowing trails circulating through an evolving vector field.
   * - growth / GrowthSettings
     - coral, forest, electric
     - Branching shoots with fading older generations.
   * - starfield / StarfieldSettings
     - drift, warp, spiral
     - Stars approaching the camera, with depth, streaks and rotation.

.. code-block:: python

   from bruhanimate import effects

   effects.flow.play(preset="neon", fps=60, updates_per_second=30,
                     on_resize="resize", seed=42)

.. code-block:: bash

   bruhanimate play growth --preset coral
   bruhanimate play starfield --preset warp
   python -m bruhanimate.demos.flow_demo
   python -m bruhanimate.demos.growth_demo
   python -m bruhanimate.demos.starfield_demo

For a spaceship with animated engines flying through warp, run
``python -m bruhanimate.demos.warp_demo``. See :doc:`demos/warp_demo` for composition
and resize behavior.

The demos accept a typed ``preset`` argument; their defaults are neon, coral
and drift, respectively. Press q, Escape or Ctrl+C to quit. These effects do
not consume input themselves; Player routes quit keys and owns cleanup.
They are endless, so set frames/duration for bounded playback or capture.

Configuration and timing
----------------------------------------

Each update advances one simulation tick. Set ``updates_per_second`` explicitly
to control simulation speed independently of display FPS. A speed of zero freezes
motion, fading, branching and random sampling. ``color=False`` uses plain ASCII.
All settings are copied at construction; edits to a settings object do not
reconfigure a running effect. Seeded runs reproduce with equal dimensions,
settings, updates and dependency versions.

.. code-block:: python

   from bruhanimate import FlowSettings, effects

   settings = FlowSettings(count=100, speed=0.6, scale=0.09,
                           decay=0.96, palette="ocean", seed=42)
   frames = []
   effects.flow.capture(settings=settings, width=60, height=20,
                        frames=3, fps=30, updates_per_second=30,
                        on_frame=frames.append)
   assert frames and frames[-1].width == 60

**FlowSettings:** count is the fixed particle budget (1–2000). speed scales
motion in cells/tick (0–2); vertical motion compensates for tall terminal cells.
scale is spatial frequency in radians per horizontal cell (0.01–1). decay is
the retained trail brightness per tick (0–0.999). Particles wrap at edges, with
no connecting line across the viewport. The palette selects neon/ocean/ember.

**GrowthSettings:** roots is the number of new shoots per generation (1–32);
max_tips bounds concurrent live shoots (1–256) and must be at least roots.
speed controls upward motion in cells/tick (0–1.5), with twice the horizontal
scale for cell aspect. branch_chance is a per-tip, per-tick probability (0–1),
and spread is the branch angle in radians (0.1–1). decay retains old branch
brightness (0–0.999). A new generation begins after cycle_ticks (1–2000) or when
all tips leave the viewport. The palette selects coral/forest/electric.
Only live tips and a viewport-sized trail field are retained, with no unbounded
branch history. Existing shoots take priority when the tip budget is full.

**StarfieldSettings:** count is the fixed star budget (1–2000). Stars travel
from depth 1 toward the near plane at 0.08; speed subtracts depth per tick
(0–0.2). twist rotates around the view axis in radians/tick (-0.1–0.1).
zoom scales perspective projection (0.2–1). trails retains brightness each
tick (0–0.98); zero draws only the current star positions. Stars outside the
viewport or near plane recycle at depth 1. Brightness represents depth and
nearer samples win when cells overlap. Streak sampling uses a fixed budget,
so extremely large viewports can show gaps in fast streaks. This is a
self-contained visual effect, not a general mesh renderer or 3D scene API.

Composition, drawing and resize
----------------------------------------

Use the classes directly in existing Scenes, Panels or layouts. Each live
effect must have one owner; construction opens no terminal or device. Draw
copies the latest private raster without advancing or modifying earlier frames.
Close is safe before startup and on repeated calls. Blank cells paint the
background; configure Layer space transparency explicitly when overlaying.

With ``on_resize="resize"``:

* Flow retains top-left trail overlap and wraps positions into new bounds.
* Growth retains top-left trail overlap and only in-bounds tips. If none survive,
  the next update plants new roots at the new bottom edge.
* Starfield retains its 3D points, clears old screen-space trails and immediately
  reprojects into the new dimensions.

Resize never consumes randomness or advances simulation. Cropped trails are
discarded; new area starts empty. A 1x1 viewport is supported, although it cannot
show the spatial structures visible at ordinary terminal sizes.
