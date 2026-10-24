Audio Effect
============

Choose a mode through ``AudioSettings.mode`` (``AudioMode`` provides editor
completion), or discover presets with ``effects.audio.presets()``. The curated
set is ``objects``, ``tiles``, ``glow``, ``bars``, ``mirror``, ``waveform``,
and ``spectrum``. The ``minimal`` preset remains monochrome bars.

.. code-block:: python

   from bruhanimate import AudioSettings, effects

   settings = AudioSettings(mode="objects", smoothing=0.7,
                            sensitivity=1.0, noise_floor=-65)
   assert settings.mode == "objects"
   assert "objects" in effects.audio.presets()
   # To open capture in your terminal:
   # effects.audio.play(settings=settings, on_resize="resize")

Objects fills the viewport with rectangular blocks, including after resize. Bass
(20–250 Hz) grows each block from 3×3 cells to fill its allotted region completely:
neighbors touch at maximum size, including along the viewport edges. Smaller
viewports clip the minimum size. Mids (250–4,000 Hz) move blocks within their
remaining space; movement settles as they fill their regions. Treble (above
4,000 Hz) adds highlights on the blocks, and overall volume controls brightness. This is
an artistic sound-reactive scene, not a waveform or a calibrated measurement.

``tiles`` fills the viewport with separated blocks. Columns span low to high
frequencies from left to right; each block's brightness follows its frequency
range with a gentle pulse. ``glow`` blends three moving pools of light: broad
amber bass, violet mids, and smaller cyan treble highlights. Band levels control
brightness and spread; mids increase movement. Both use colored backgrounds,
with ASCII shading when ``color=False``, and fade toward silence. Resize rebuilds
the geometry while preserving motion phase. The demo uses arrow keys only;
there is no automatic mode switch.
The :doc:`../demos/audio_demo` renders these modes inside a computer monitor;
**C** switches between the original artwork and a larger rectangular frame.
Standalone effects still use their entire supplied buffer.

Readable response
-----------------

Frequency levels sum energy across each band, so diffuse sounds such as cymbals
remain visible alongside a stronger bass tone. Window compensation keeps a
band's amplitude approximately equal to a sine's peak amplitude; overall volume
uses RMS. Bar spacing eases into a logarithmic scale, giving mids and treble more
screen space instead of repeating a handful of bass bins across the left side.
Very wide viewports can still repeat bins at the capture chunk's resolution.

Levels use a fixed dB scale; neither chunks nor individual bands are normalized
to their own peak. Quiet sounds remain visibly quieter. ``noise_floor`` is the
bottom of that scale, in dB relative to full-scale samples (default -65, allowed
-120 through -1). Raise it, for example to -40, to suppress background noise;
lower it to include quieter detail. ``sensitivity`` scales input amplitude before
level conversion; zero suppresses response. These controls do not change playback
volume or establish sound-pressure levels. The lower default floor retains more
quiet detail; use ``noise_floor=-55`` to restore the earlier display threshold.

``smoothing`` is release retention per simulation tick: 0 responds immediately,
0.7 falls gradually, and 1 holds prior levels. Attack retention is capped at 0.25
so transients still rise promptly. Motion, peak decay, and history use simulation
ticks; 30 updates/sec is the demo's reference rate. Drawing never advances time
or reads a new audio chunk. Analysis uses one FFT per tick and caches its window
and frequency bins. Windows uses the device's actual sample rate and the channel
with the greatest chunk energy, so right-only or opposite-phase stereo is visible.

Bars have a green/yellow/red height gradient and falling peak caps. Mirror shares
the frequency layout; tiny viewports remain drawable. ``bar_gain`` multiplies
Bars/Mirror display height and peak caps, with a default of 2 so moderate audio
uses more of the viewport. Values clip at full height; Mirror reaches both edges
symmetrically. Set ``bar_gain=1`` for the original height, increase it for taller
bars, or use 0 to hide them. This is a fixed display multiplier, not automatic
normalization; it does not change analysis or the other modes. ``compact=True``
removes gaps between columns, as used by the Bars/Mirror demo.

.. code-block:: python

   from bruhanimate import AudioSettings, effects

   settings = AudioSettings(mode="mirror", bar_gain=2.5, compact=True)
   assert settings.bar_gain == 2.5
   # effects.audio.play(settings=settings, on_resize="resize")

Spectrum paints every row
with low pitches at the bottom and scrolls newest samples in from the right.
Waveform is a volume-history envelope, not a sample-by-sample oscilloscope.
Objects retains a subtle idle drift; Tiles and Glow fade to the background
when their smoothed audio levels reach silence.

Capture starts only in ``start()``. Player/Scene owns cleanup; changing mode with
``set_mode`` validates the typed name and clears stale pixels without restarting
capture. Resize retains capture, phase and smoothed levels; the object field
reflows on the next update. Synthetic audio tests cover rendering and cleanup;
physical-device behavior depends on the optional backend. See
:doc:`../platform_checks` for explicit native checks.

Removed modes in 1.3
--------------------

The experimental modes and same-named presets ``radial``, ``rain``, ``tunnel``,
``ripple``, ``vortex``, ``wave``, ``interference``, ``lightning``, ``aurora``,
``orbit``, ``orbit_gradient``, ``scope``, ``grid``, ``helix``, ``lissajous``,
``sunburst``, ``mandala``, ``comet``, ``weave``, ``fireworks``, ``starfield``,
and ``bounce`` have been removed from the API,
CLI discovery, and demo. Existing calls using them now raise validation errors.
Use ``objects``, ``tiles``, or ``glow`` for a screen-wide reactive scene,
or ``waveform``/``spectrum`` for sound history. There are no
silent aliases. Audio levels and smoothing also look different from older builds;
retune ``sensitivity`` and ``noise_floor`` if needed.

.. automodule:: bruhanimate.bruheffect.audio_effect
   :members:
   :undoc-members:
   :show-inheritance:
