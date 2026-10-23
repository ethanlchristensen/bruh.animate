Terminal utilities
==================

These modules support the animation player: terminal cells, Screen access,
ASCII art, effect names, and errors. Start with :doc:`../concepts` for how they
fit together, or use :doc:`../grid` for drawing logical boards.

* **Buffer (bruhffer):** a rectangular cell grid, clipped drawing, frame copying,
  and changed-cell comparison. Dimensions are height/width; drawing uses x/y.
* **Screen (bruhscreen):** Windows console or curses-based terminal access,
  keyboard events, frame output, resize detection, and restoration. Most scripts
  should use play rather than managing a Screen themselves.
* **ASCII art (bruhimage):** bundled text art and PyFiglet text-to-ASCII helpers.
  These helpers do not load or process raster image files.
* **Errors (bruherrors):** exceptions for invalid animation settings and terminal
  failures, including resize.
* **Types/constants (bruhtypes, utils):** effect names, directions, and shared
  character/color tables used by built-in effects.

.. toctree::
   :maxdepth: 1

   bruherrors
   bruhffer
   bruhimage
   bruhscreen
   bruhtypes
   utils
