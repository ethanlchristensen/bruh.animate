SVG, PNG, GIF, and MP4 export
=============================

Use ``save_svg`` for dependency-free snapshots. Install the optional export extra
for PNG, GIF, and MP4; the base animation installation remains unchanged.

.. code-block:: shell

   pip install "bruhanimate[export]"
   # In a source checkout:
   uv sync --locked --extra export

MP4 uses the FFmpeg executable supplied by imageio-ffmpeg, without a separate
FFmpeg installation on supported Windows, Linux, and macOS wheels. Files play in
ordinary image/video viewers. These exports do not require a .cast player.

Snapshots
---------

Capture supplies immutable ``Frame`` objects. Export them without opening a
terminal, consuming input, or advancing the animation again:

.. code-block:: python

   from pathlib import Path
   from tempfile import TemporaryDirectory
   from bruhanimate import ExportStyle, capture, save_svg

   frames = []
   capture("plasma", on_frame=frames.append, frames=1, width=20, height=6)
   with TemporaryDirectory() as directory:
       save_svg(frames[0], Path(directory) / "plasma.svg",
                style=ExportStyle(cell_size=(10, 20), background=(8, 8, 16)))

``save_png(frame, path, style=...)`` has the same interface. ``ExportStyle`` is a
frozen dataclass with discoverable ``cell_size``, ``font_size``, ``font``,
``foreground``, and ``background`` fields. Dimensions and font size are pixels;
colors are RGB integer tuples. Raster output defaults to Pillow's bundled font.
Pass a local TrueType/OpenType font path for your preferred monospace font.
SVG uses the viewer's monospace font and does not embed that file.

Animation
---------

``export_animation`` accepts named effects, owned Animation instances, or an
``effect_factory`` just like capture. ``ExportFormat`` completes ``"gif"`` and
``"mp4"``; omitting ``format`` infers it from the filename suffix.

.. code-block:: python

   from pathlib import Path
   from tempfile import TemporaryDirectory
   from importlib.util import find_spec
   from bruhanimate import export_animation
   from bruhanimate.demos.routing_demo import build_scene

   if find_spec("PIL") and find_spec("imageio_ffmpeg"):
       with TemporaryDirectory() as directory:
           export_animation(Path(directory) / "route.mp4",
                            effect_factory=build_scene, width=50, height=15,
                            duration=1, fps=20, updates_per_second=30)

For a persistent clip, pass your own path (for example ``"route.mp4"``).
The parent directory must exist. Existing files raise ``FileExistsError`` unless
``overwrite=True``. Files are published only after rendering and encoding finish;
failures remove temporary output and preserve any previous destination.

Timing, ownership, and limits
-----------------------------

* Supply a finite ``frames`` or ``duration`` bound. Time is virtual; rendering
  does not sleep. Seeded effects follow :doc:`capture` reproducibility rules.
  ``on_complete="exit"`` stops when content finishes; ``"hold"`` captures until
  the bound. Zero bounds write no file and start no content or encoder.
* N frames play for N/FPS seconds. GIF delays round to 10 ms, so FPS must not
  exceed 100. GIF loops forever. MP4 is silent H.264 video with streamed frames;
  odd pixel dimensions gain one black padding row/column for codec compatibility.
* GIF retains RGB frames up to ``gif_max_pixels`` (default 20 million pixels
  across frames). Encoding can use additional memory. Choose MP4 for longer clips,
  or reduce dimensions/duration. MP4 retains only current rendering state.
* Dimensions remain fixed. No keyboard or resize events are generated. Resourceful
  animations still start their own devices/processes. Export owns content and
  closes it on completion or failure, and closes/reaps its encoder. As in Player,
  KeyboardInterrupt ends capture normally and can save the frames captured so far.
* Single-cell glyphs and ANSI colors (16/256/RGB), bold, dim, underline, and inverse
  are supported. Other SGR attributes, wide/combining glyphs, and cursor escapes
  raise errors. Terminal theme colors are not read: exports use the xterm palette
  and explicit defaults. Raster glyphs are clipped to their cells.

API
---

.. automodule:: bruhanimate.export
   :members: ExportStyle, ExportFormat, save_svg, save_png, export_animation
