Water, smoke, cloth, and procedural worlds
==========================================

Run ``python -m bruhanimate.demos.nature_demo`` for a six-panel gallery. Each
panel owns its simulation, updates at 30 ticks/sec, and resizes without a restart.
Presentation defaults to 60 FPS. Press q, Escape, or Ctrl+C to quit.
No extra dependencies, audio capture, or external data are needed.

Discover settings and presets
-----------------------------

Use the typed catalog for editor completion of both settings and preset names.
``effects.names()`` lists registered names; ``effects.water.presets()`` returns
independent settings copies keyed by preset name. ``effects.water.defaults()``
returns a fresh WaterSettings. Editing one never changes registry defaults.

.. code-block:: python

   from bruhanimate import effects

   print(effects.names())
   print(effects.water.presets())
   effects.water.play(preset="rain", seed=42, duration=10,
                      fps=60, updates_per_second=30, on_resize="resize")

.. list-table:: Built-ins and presets
   :header-rows: 1
   :widths: 18 28 54

   * - Effect / settings
     - Presets
     - Behavior
   * - water / WaterSettings
     - pond, rain, storm
     - Reflecting waves with interacting, damped ripples.
   * - diffusion / DiffusionSettings
     - coral, spots, stripes, organic
     - Gray–Scott reaction–diffusion. Organic uses shaded, scattered seeds.
   * - smoke / SmokeSettings
     - plume, ink, windy
     - Advected density; smoke rises, ink sinks. Supports solid obstacle cells.
   * - metaballs / MetaballsSettings
     - lava, orbit, outline
     - Implicit blobs merge and separate; filled surfaces or outlines.
   * - cloth / ClothSettings
     - flag, checker, banner
     - Pinned, shaded traveling folds, carrying patterns, text, or custom ASCII.
   * - terrain / TerrainSettings
     - hills, mountains, contours
     - Perspective terrain flyover with slope lighting or elevation contours.

CLI discovery uses the same registry:

.. code-block:: console

   bruhanimate list
   bruhanimate info water
   bruhanimate presets terrain
   bruhanimate play smoke --preset ink --on-resize resize
   bruhanimate play cloth --preset banner --set text=HELLO --on-resize resize
   bruhanimate play diffusion --preset organic --seed 42 --on-resize resize

All settings validate types, finite numbers, ranges, and Literal choices before
allocation. ``color=False`` gives plain ASCII. Seeds are local to each effect;
equal settings, sizes, seeds, and updates reproduce output in the same dependency
versions. Settings are copied by the new effects; editing them after construction
does not reconfigure a running simulation.

Water and smoke controls
------------------------

WaterSettings.wave_speed is cells per tick (0.05–0.7), damping retains motion
(0–1), drop_chance is a probability per tick (0–1), and strength is random-drop
displacement (0–5). The speed cap keeps the finite-difference scheme stable.
``drop(x, y, strength)`` injects a smooth local disturbance; strength accepts
[-5, 5]. Outside coordinates are ignored. It becomes visible on the next update.

.. code-block:: python

   from bruhanimate import Buffer, WaterEffect, WaterSettings, play

   def water(buffer: Buffer) -> WaterEffect:
       effect = WaterEffect(buffer, " ", WaterSettings(drop_chance=0, seed=42))
       effect.drop(buffer.width() // 2, buffer.height() // 2, strength=2)
       return effect

   play(effect_factory=water, duration=10, updates_per_second=30, on_resize="resize")

SmokeSettings.rise is cells per tick (0–0.9); turbulence controls horizontal
drift (0–0.9), decay retains density (0–1), and diffusion mixes neighboring cells
(0–0.25). source_width is a fraction of the viewport width (0.01–1); intensity
controls source density (0–1). ``style="ink"`` reverses the vertical flow.
This is an artistic advected field, not a pressure-solving fluid simulation.
``set_obstacles(iterable_of_xy_cells)`` copies a new solid mask, clips outside
coordinates and clears density there. Passing an empty iterable removes it.

.. code-block:: python

   from bruhanimate import Buffer, SmokeEffect, SmokeSettings, play

   def smoke(buffer: Buffer) -> SmokeEffect:
       effect = SmokeEffect(buffer, " ", SmokeSettings(seed=42))
       y = buffer.height() // 2
       effect.set_obstacles((x, y) for x in range(buffer.width() // 3,
                                                buffer.width() * 2 // 3))
       return effect

   play(effect_factory=smoke, duration=10, updates_per_second=30, on_resize="resize")

Cloth carrying your own art
---------------------------

ClothSettings.pattern accepts ``"flag"``, ``"checker"``, or ``"text"``; text
defaults to BRUH. amplitude is a fraction of viewport height, wavelength counts
cycles across the cloth, and speed is radians per tick. The left edge is pinned.
This uses kinematic waves rather than a spring/force solver.
Custom art overrides the selected pattern. Supply text or a sequence of rows;
rows are copied, space-padded, centered at their original size, and clipped.
ANSI escapes and wide/combining glyphs are rejected. ``set_image(None)`` restores
the configured pattern; changes appear on the next update or resize.

.. code-block:: python

   from bruhanimate import ClothEffect, ClothSettings, play, text_to_image

   art = text_to_image("BRUH", font="small")
   play(effect_factory=lambda buffer: ClothEffect(
       buffer, " ", ClothSettings(amplitude=0.1), image=art),
       duration=10, fps=60, updates_per_second=30, on_resize="resize")

Metaballs, terrain, and reaction–diffusion
------------------------------------------

MetaballsSettings.count selects 1–20 blobs; radius is a fraction of the shorter
visual viewport axis. Cells are treated as twice as tall as they are wide.
speed is radians per tick; threshold sets the visible isosurface. Set filled=False
for outlines. Blobs combine their fields, so overlapping surfaces merge.

TerrainSettings.speed is world units per tick; scale is noise frequency per
world unit, roughness scales elevation, and horizon is a fraction of viewport
height. style selects shaded terrain or contours. A fixed seeded tile provides
four noise octaves; forward travel wraps periodically without growing memory.
The camera height is fixed, so tall nearby terrain can fill the view.

Diffusion remains the existing reaction–diffusion built-in. New keyword-only
options ``shading=True`` and ``seed_pattern="scattered"`` add concentration
shading and seeds across the viewport. The ``organic`` preset enables both;
older presets retain their configuration. ``steps_per_frame`` remains the
historical name for numerical substeps per simulation tick. ``set_parameters``
validates finite feed/kill rates in [0, 1] atomically before changing them.

Lifecycle and resize
--------------------

These effects run indefinitely; use Player's frames or duration limits to stop.
Construction acquires no external resources, draw only copies the last raster,
and close is safe before start and on repeated calls. Player/Scene/Panel own
their children as usual; do not share an effect between owners. Public controls
use local coordinates and never poll input. Wire bindings through Player if needed.

* Water preserves top-left displacement and velocity; added cells are still.
* Smoke preserves top-left density and obstacle cells; added cells are empty.
  Its source moves to the new top/bottom on the next tick.
* Diffusion preserves concentrations; added cells start at U=1/V=0.
* Metaballs and cloth remap at their existing phase; cloth retains its ASCII art.
* Terrain keeps its noise tile and camera position and rebuilds the view.

Shrinking discards cropped simulation cells and obstacles. Resize advances no
time and consumes no randomness. See :doc:`resize` for the shared contract.
Individual demos are available as water_demo, smoke_demo, metaballs_demo,
cloth_demo, terrain_demo, and diffusion_demo under ``bruhanimate.demos``.
