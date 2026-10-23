Demos
=====

This section contains content related to the demos package.

Overview
--------
Each demo is a standalone runnable example of an effect or composed scene. There are two ways to run a demo:

**From Python:**

.. code-block:: python

   from bruhanimate import plasma_demo
   plasma_demo.run()

**From the command line:**

.. code-block:: bash

   python -m bruhanimate.demos.plasma_demo

Available Demos
---------------

- **dashboard_demo** — Nested layouts, live solver statistics, status bar, and animated panels.

- **windows_demo** — Four bouncing windows with plasma, fire, snow, and Matrix rain.

- **tv_demo** — Plasma inside a retro TV, snow behind it, and a temporary channel badge.

- **beam_demo** — Clipped snow, independently paced beam solver, and timed overlay.

- **audio_demo** — System audio visualizer (EQ bars, waveform, mirror).
- **static_demo** — Static background fill.
- **offset_demo** — Scrolling offset background.
- **noise_demo** — Coloured random-noise pixels.
- **stars_demo** — Blinking star field.
- **snow_demo** — Falling snow with ground accumulation.
- **rain_demo** — Rain with wind and collision.
- **plasma_demo** — Animated plasma with colour and info overlay.
- **gol_demo** — Conway's Game of Life with rainbow decay.
- **matrix_demo** — Cascading digital rain.
- **twinkle_demo** — Twinkling star characters.
- **fire_demo** — Fire simulation with heat spots.
- **firework_demo** — Coloured firework explosions.
- **julia_demo** — Animated Julia-set fractal.
- **line_demo** — Bresenham line drawing.
- **holiday** — Festive holiday scene.
- **boids_demo** — Reynolds flocking simulation.
- **sand_demo** — Falling-sand cellular automaton.
- **diffusion_demo** — Gray-Scott reaction-diffusion (cycles coral/spots/stripes).
- **automaton_demo** — Wolfram 1-D elementary CA (cycles rules 30/90/110/184).
- **voronoi_demo** — Animated Voronoi diagram.
- **perlin_demo** — Smooth animated noise field.

.. toctree::
   :maxdepth: 2

   audio_demo
   beam_demo
   tv_demo
   windows_demo
   dashboard_demo
   static_demo
   offset_demo
   noise_demo
   stars_demo
   snow_demo
   rain_demo
   plasma_demo
   gol_demo
   matrix_demo
   twinkle_demo
   fire_demo
   firework_demo
   julia_demo
   line_demo
   holiday
   boids_demo
   sand_demo
   diffusion_demo
   automaton_demo
   voronoi_demo
   perlin_demo

   shared_player_demo
   terminal_demo

   grid_demo
