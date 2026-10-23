Bruheffect
==========

This section contains content related to the bruheffect package.

Overview
--------
The ``bruheffect`` package provides a collection of terminal animation effects. Every
effect is configured through a **settings dataclass** — pass one to the effect constructor
to tune its behaviour, or omit it to get sensible defaults. All runtime-adjustable
parameters are also exposed as ``set_*`` methods.

Effects
-------

- **base_effect** — Abstract base class that all effects inherit from.
- **static_effect** — Fills the screen with a static background character.
- **offset_effect** — Scrolling offset background. Configure with ``OffsetSettings``.
- **noise_effect** — Random noise pixels. Configure with ``NoiseSettings``.
- **star_effect** — Blinking star field built on ``NoiseEffect``. Configure with ``StarSettings``.
- **snow_effect** — Falling snow with wind and ground accumulation. Configure with ``SnowSettings``.
- **rain_effect** — Falling rain with wind direction and collision. Configure with ``RainSettings``.
- **plasma_effect** — Animated sine-wave plasma. Configure with ``PlasmaSettings``.
- **matrix_effect** — Cascading random-character digital rain. Configure with ``MatrixSettings``.
- **game_of_life_effect** — Conway's Game of Life with optional decay. Configure with ``GameOfLifeSettings``.
- **twinkle_effect** — Characters that pulse in brightness. Configure with ``TwinkleSettings``.
- **fire_effect** — Particle-based fire simulation. Configure with ``FireSettings``.
- **firework_effect** — Firework explosions with multiple burst patterns. Configure with ``FireworkSettings``.
- **julia_effect** — Animated Julia-set fractal.
- **draw_lines_effect** — Bresenham line drawing onto the buffer. Configure with ``DrawLinesSettings``.
- **audio_effect** — System audio visualizer (bars, waveform, mirror, and 20+ modes). Configure with ``AudioSettings``.
- **boids_effect** — Reynolds flocking simulation (separation, alignment, cohesion). Configure with ``BoidsSettings``.
- **sand_effect** — Falling-sand cellular automaton; particles pile up at the bottom. Configure with ``SandSettings``.
- **diffusion_effect** — Gray-Scott reaction-diffusion; produces organic spots and stripes. Configure with ``DiffusionSettings``.
- **automaton_effect** — Wolfram 1-D elementary cellular automaton scrolling downward. Configure with ``AutomatonSettings``.
- **voronoi_effect** — Animated Voronoi diagram with drifting seed points. Configure with ``VoronoiSettings``.
- **perlin_effect** — Smooth animated noise field from multiple sine-wave octaves. Configure with ``PerlinSettings``.
- **settings** — All settings dataclasses live here.
- **registry** — Discoverable effect registry; create effects by name, list presets, register custom effects.

.. toctree::
   :maxdepth: 2

   settings
   registry
   audio_effect
   terminal_effect
   base_effect
   static_effect
   offset_effect
   noise_effect
   star_effect
   snow_effect
   rain_effect
   plasma_effect
   matrix_effect
   game_of_life_effect
   twinkle_effect
   fire_effect
   firework_effect
   julia_effect
   draw_lines_effect
   boids_effect
   sand_effect
   diffusion_effect
   automaton_effect
   voronoi_effect
   perlin_effect
