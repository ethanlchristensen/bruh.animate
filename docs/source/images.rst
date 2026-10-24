ASCII images, transitions, masks, and styling
========================================================

An image here is a rectangular arrangement of terminal cells: ASCII artwork,
plain text, or rows returned by ``text_to_image`` (pyfiglet). It is not a bitmap
file loader. ``ImageEffect`` and the image transitions implement the ordinary
``Animation`` protocol. Masks and styling belong to ``Layer`` and therefore also
work with labels, callbacks, solver drawings, and other animations. No additional
public base-image hierarchy or legacy renderer is required.

Try ``python -m bruhanimate.demos.image_demo`` for six resizable panels, or
``python -m bruhanimate.demos.tv_demo`` for alternating entrances over plasma.

Typed image effects
------------------------------

All helpers are exported from ``bruhanimate``. Editor completion shows constructor
options; ``DissolveDirection`` offers ``"in"`` and ``"out"``.
``WipeDirection`` offers ``"left"``, ``"right"``, ``"up"``, and ``"down"``.

.. list-table::
   :header-rows: 1
   :widths: 26 40 34

   * - Effect
     - Behavior
     - Main controls
   * - ``ImageEffect``
     - Display/pan text; optional typewriter reveal
     - ``velocity``, ``characters_per_second``
   * - ``GlitchImageEffect``
     - Fly in from the left with changing symbols and jitter
     - ``characters_per_second``, ``travel_time``, ``seed``
   * - ``FocusImageEffect``
     - Assemble scattered glyphs into their final positions
     - ``duration``, ``scatter=(columns, rows)``, ``seed``
   * - ``DissolveImageEffect``
     - Reveal or remove glyphs in random order
     - ``duration``, ``direction``, ``seed``
   * - ``WipeImageEffect``
     - Reveal a straight edge across the image bounds
     - ``duration``, ``direction``, ``reverse``

.. code-block:: python

   from bruhanimate import (
       FocusImageEffect, Layer, Scene, TextStyle, effect_registry, play, text_to_image,
   )

   def build(buffer):
       plasma = effect_registry.create("plasma", buffer, " ", seed=7)
       title = FocusImageEffect(
           text_to_image("bruh", font="small"), duration=2.5,
           scatter=(8, 3), seed=42, repeat=True, reverse=True,
           hold_duration=3, repeat_delay=1,
       )
       return Scene(
           Layer(plasma, updates_per_second=30),
           Layer(title, style=TextStyle(foreground=231, bold=True),
                 preserve_background=True),
       )

   play(effect_factory=build, duration=10, on_complete="hold", on_resize="resize")

The four transitions share ``x``/``y`` (None centers each axis),
``repeat``, ``reverse``, ``hold_duration``, and ``repeat_delay``. Options are set at construction.
``duration`` reports transition seconds, excluding hold/gap; Glitch derives this
from its glyph count, launch rate, and travel time. Glitch, Focus, and Dissolve
also accept ``seed``; Wipe is deterministic and needs no seed. Non-space glyphs alone animate;
spaces and unseen glyphs are transparent. Input must be plain single-cell text,
without ANSI escapes, wide glyphs, or combining marks. Use Layer styling for color.

Focus scatter is a pair of non-negative integer offsets relative to each glyph's
final position. It is independent of terminal size. Glyphs interpolate linearly,
and overlapping particles paint in original row order. On completion the image
is exact. Dissolve ``"in"`` starts blank and ends with the image; ``"out"`` starts
with the image and ends blank. Wipe direction names describe the edge motion:
``right`` reveals from the left; ``left`` from the right; ``down`` from the top;
``up`` from the bottom. Its reverse leg retracts the same edge.

Timing, completion, and ownership
--------------------------------------

Only ``update(dt)`` advances time, in simulation seconds. Drawing does not consume
randomness or advance state. Seeds make initial scatter/order/glitches reproducible;
repeated cycles reuse them. Duration and speeds must be positive and finite;
hold/gap times must be finite and non-negative. Empty images finish immediately.

Without repetition, ``finished`` becomes True after the transition and the final
state remains visible. Use ``on_complete="hold"`` to keep a background running.
With ``repeat=True``, the transition completes, holds its final state, paints
nothing during the gap, and starts again. For a dissolve exit the final state is
already blank. Non-empty repeated transitions report ``finished=False`` throughout.
Large updates can cross multiple cycles without performing work per skipped cycle.

Set ``reverse=True`` to add a return leg after the hold. The same transition is
sampled backwards, so Glitch retraces its flight and symbols, Focus scatters back
along its original paths, and Dissolve removes the last-revealed glyphs first.
Both legs take ``duration`` seconds. A repeating cycle now lasts
``2 * duration + hold_duration + repeat_delay``; the gap starts after the exit.
This is the behavior used by the TV and image showcase demos.

For a single round trip (``reverse=True, repeat=False``), completion waits until
``2 * duration + hold_duration`` and retains the initial state: blank for Glitch
or Wipe or dissolve-in, scattered glyphs for Focus, and the full image for dissolve-out.
Repeating cycles hide all output during their gap. The default ``reverse=False``
preserves the existing one-way behavior. Resizing during the hold or reverse leg
does not reset time or change paths/order.

Resize preserves time, scatter/order, and completion. Centered images recenter;
explicit coordinates stay fixed. Drawing clips; offscreen glyphs still progress.
Focus particles and Glitch jitter can extend beyond the final image rectangle;
use a mask, Layer region, or Panel when those movements need a boundary.

Scene owns each animation once. These image effects own no children or external
resources and consume no input. Startup and cleanup are idempotent and do not
restart progress. Configure keyboard routing separately through Player.

For a timed playlist of different animations, use :doc:`sequencing`. The TV demo
uses AnimationSequence to own and replace each transition while plasma runs.

Masks for any animation
------------------------------

``Layer(mask=...)`` accepts a ``CellMask`` callable with signature
``(x: int, y: int, size: tuple[int, int]) -> bool``. Coordinates are destination
cells; size is (width, height). True permits painting. Masks intersect ``region``
and transparency rules without translating the child or changing its clock.
They run during draw and must be pure: do not read input, consume randomness,
or advance simulation there. Derive geometry from size to follow resizing.

``ImageMask`` snapshots ASCII rows, allowing non-space positions. ``x`` and ``y``
are integer positions or None for centering. ``invert=True`` allows the complement,
including cells outside the image. Ragged rows and empty masks are supported.
Masks are immutable and own no lifecycle resources.

.. code-block:: python

   from bruhanimate import ImageMask, Layer, Scene, effect_registry, play, text_to_image

   def build(buffer):
       plasma = effect_registry.create("plasma", buffer, " ", seed=7)
       return Scene(Layer(plasma, mask=ImageMask(text_to_image("bruh", font="small"))))

   play(effect_factory=build, duration=5, on_resize="resize")

This paints plasma only through the lettering. The TV uses a custom CellMask for
its sloping monitor opening; the same mask applies to plasma and animated text.

Styling and background preservation
-----------------------------------------

``Layer(style=TextStyle(foreground=231, background=None, bold=True))`` styles any
visible single-cell child output. Explicit palette colors (0..255) override child
colors; None leaves them alone. True enables bold; False leaves child bold alone.
The widget API still accepts the same TextStyle class and imports.

``preserve_background=True`` uses the already composed lower cell's background
color, while retaining the upper glyph and its foreground attributes. An explicit
``style.background`` wins. Basic/bright ANSI colors, 256-color palettes, RGB colors,
and resets are supported. An unstyled/transparent lower cell supplies the terminal
default background. This is cell-background composition, not alpha blending.
Foreground and other lower-layer attributes are not inherited.

Plain spaces still paint unless ``transparent=True``; ANSI-styled spaces remain
visible. Transparency is evaluated before Layer styling. None cells never paint.
Only layers using these options parse cell styles; ordinary composition retains
its existing path. Children still receive isolated buffers; lower animations are
not read directly or borrowed by upper animations.

API reference
------------------------------

.. automodule:: bruhanimate.masks
   :members:

.. automodule:: bruhanimate.image
   :members:
