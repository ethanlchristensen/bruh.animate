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

Every demo defaults to ``on_resize="resize"`` and continues playing when the
terminal changes size. The typed ``on_resize`` argument also accepts ``"raise"``
if you want resizing to stop playback. See :doc:`../resize` for the policy.

All built-in simulations adapt their areas using documented state policies.
The dashboard reflows its layout. The TV demo recenters its original computer
artwork; fixed layer regions and moving window bounds are not rebuilt.
Cycling showcases preserve their phase clocks
and notify inactive effects too, so later phases use the new viewport.

The :doc:`nature_demo` gallery combines six natural/procedural effects.
See :doc:`../natural_effects` for settings and presets.

Available Demos
---------------

- **routing_demo** — Source pulse, route trace, moving marker, and arrival ripple over snow.

- **image_demo** — Six resizable panels showcasing transitions, Wipe, masks, and styling.

- **dashboard_demo** — Nested layouts, live solver statistics, status bar, and animated panels.

- **windows_demo** — Five bouncing windows with plasma, fire, snow, Matrix rain, and live-audio Mirror.

- **tv_demo** — Plasma inside the original v0.2 computer artwork, snow behind it, and cycling Glitch/Focus/Dissolve/Wipe lettering.

- **beam_demo** — Clipped snow, independently paced beam solver, and timed overlay.

- **audio_demo** — Seven sound-reactive modes, starting with a screen-wide field of objects; left/right selects modes.
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

   nature_demo
   water_demo
   smoke_demo
   metaballs_demo
   cloth_demo
   terrain_demo
   audio_demo
   beam_demo
   tv_demo
   image_demo
   routing_demo
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
