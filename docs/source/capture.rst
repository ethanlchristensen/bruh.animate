Seeded capture and recording
================================

Use the typed catalog to discover effects, presets, and settings, then capture
frames or write a terminal recording without an attached terminal. These APIs
use the same Player lifecycle and simulation loop as interactive playback.

Repeatable effects
------------------

Every built-in settings dataclass has a keyword-only ``seed: int | None``.
Non-negative integers, including zero, select independent Python and NumPy random
streams. ``None`` uses fresh entropy. Running another effect cannot change this
effect's random sequence. Process-global RNG state is untouched.

.. code-block:: python

   from bruhanimate import effects

   settings = effects.snow.preset("light")  # SnowSettings, with field completion
   settings.seed = 42
   effects.snow.play(settings=settings, duration=2)

``play``, ``Player``, ``capture``, ``record``, and ``effect_registry.create`` also
accept a ``seed`` override for named effects. It overrides the seed in the selected
settings/preset on an independent copy. Passing ``None`` preserves the selected
seed; use a settings copy with ``seed=None`` to return to fresh entropy.
Static and Julia have no settings or randomness and reject seed overrides.
For instances/factories, configure randomness when constructing the animation.

Reproduction requires fresh instances with matching seed, settings, dimensions,
update sequence, external inputs, and dependency versions. Output is not guaranteed
identical across Python/NumPy or library releases. Seeds control visual randomness,
not live audio or process output. Starting the same instance again does not rewind
its state. Global ``random.seed`` and ``numpy.random.seed`` no longer seed built-ins.

Stream immutable frames
-----------------------

.. code-block:: python

   from bruhanimate import Frame, effects

   def inspect(frame: Frame) -> None:
       print(frame.index, frame.time, frame.width, frame.height)
       print(frame.text())

   effects.snow.capture(
       on_frame=inspect, preset="light", seed=42,
       width=40, height=12, frames=4, fps=60, updates_per_second=30,
   )

Type ``effects.`` for built-ins and ``effects.snow.capture(preset=...)`` for snow
preset completion. ``Frame.cells`` is a tuple of tuple rows containing immutable
strings, with no references to mutable Buffers or twinkle cells. ``Frame.text()``
joins rows with newlines, preserving ANSI SGR. Frame indices start at zero.
Transparent cells remaining after composition become spaces.

``capture`` requires ``frames`` or ``duration``. Time is virtual: it starts at
zero after startup and advances at positive ``fps`` without sleeping. The first
frame follows one update, as in Player. Frames occur at ``i / fps`` before the
duration deadline, subject to floating-point precision. Fixed
``updates_per_second`` rates do not drop offline ticks. Callback execution and
rendering take no virtual time. Completion exits by default; use
``on_complete="hold"`` to continue until a bound. Zero bounds construct/start
no content. No input events or resizes are generated.

Top-level ``capture`` also accepts owned Animation objects, Scenes, and factories:

.. code-block:: python

   from bruhanimate import ImageEffect, Scene, capture

   capture(
       Scene(ImageEffect(["Hello, recording!"])),
       on_frame=lambda frame: print(frame.text()),
       width=24, height=4, frames=2,
   )

The synchronous callback receives each snapshot before the next update. Capture
retains only current rendering state; memory is bounded unless your callback
stores frames or the animation retains history. Owned content is closed after
startup/update/draw/callback failures, then exceptions propagate. KeyboardInterrupt
ends normally, as in Player. Resourceful animations still run ``start`` and
``close``: headless does not disable audio acquisition or custom devices. Use
prerecorded or stubbed inputs in tests. Never share an animation between owners.

Write a .cast recording
--------------------------

.. code-block:: python

   from io import StringIO
   from bruhanimate import effects

   output = StringIO()
   effects.snow.record(output, preset="light", seed=42, duration=2,
                       width=40, height=12)
   print(output.getvalue().splitlines()[0])  # Header; stream stays open

Pass a path instead of a text stream to save a file, or use the CLI:

.. code-block:: shell

   bruhanimate record snow snow.cast --preset light --seed 42 --duration 5
   bruhanimate record fire fire.cast --seed 42 --frames 120 --width 80 --height 24
   bruhanimate info snow
   bruhanimate play snow --preset light --seed 42 --duration 5

Discovery and ``--set FIELD=VALUE`` remain available. ``--seed`` overrides even
``--set seed=...``. Use ``--overwrite`` (``overwrite=True`` in Python) explicitly
to replace an existing file. Capture options are validated before opening a path;
rendering or writing failures may leave a partial recording. Paths use UTF-8;
borrowed text streams receive writes at their current position and remain open.

The writer streams `asciicast v2
<https://docs.asciinema.org/manual/asciicast/v2/>`_ newline-delimited JSON:
a size/version header and output events with absolute virtual timestamps. Only
changed cells are written. The final event restores styles, cursor visibility,
and autowrap at the last captured frame's timestamp, including unchanged frames.
Thus N frames span ``(N - 1) / FPS`` seconds; a one-frame recording has timestamp
zero. Zero frames produce a header-only file. No input, environment, host
timestamps, or audio are recorded. No extra export dependency is needed.

Cells must contain one printable character, optionally ANSI SGR styled. Wide or
combining glyphs, cursor escapes, and other controls are rejected during recording.
Ambiguous-width glyphs assume one terminal column, as in :doc:`grid`.
See :doc:`exports` for SVG/PNG snapshots and GIF/MP4 clips. Headless capture
uses fixed dimensions and does not reconstruct interactive resize events.

Recording does not install a playback application or add a Windows ``.cast``
replay command. External playback requires a compatible asciinema player.
Use ``play`` or the bundled demos to run animations directly in your normal
Windows terminal without an external recording player.

API
---

.. automodule:: bruhanimate.capture
   :members:
