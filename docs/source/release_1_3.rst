Release 1.3.0
=============

This release extends the composable Animation/Scene/Player API. Base installation
dependencies are unchanged; the optional ``export`` extra adds raster/video tools.

* ASCII transitions: typewriter reveal on ImageEffect, Glitch, Focus, Dissolve,
  and directional Wipe. Transitions support holds, repeats, gaps, and reverse
  playback while backgrounds continue running. See :doc:`images`.
* Generic Layer masks and styling, including ImageMask and preservation of the
  current lower-layer background color. These also work with non-image content.
* Public AnimationSequence and SequenceStep for timed factory-owned playlists,
  including finite completion, frozen holds, blank gaps, repetition, and resize.
  See :doc:`sequencing` for large-time-step and ownership contracts.
* All built-in simulations now adapt to viewport changes without restarting or
  advancing time/randomness. Each adapter has an explicit state policy; see
  :doc:`resize`. Custom BaseEffect subclasses retain the clipping fallback.
* Demos enable live resize by default. The TV uses the original computer artwork,
  masked plasma, and a four-transition playlist; the six-panel image showcase
  demonstrates transitions, styling, masks, and sequencing.
* Matrix character changes repaint independently of its color clock. Unix
  batched output applies unsupported-character fallback at the write boundary.
* Faster Scene composition and vectorized Plasma rendering, plus portable CPU
  and native Screen benchmarks. See :doc:`performance` for measurements/limits.

* Typed PathEffect, PulseEffect, and RippleEffect board accents, with a complete
  routing demo. See :doc:`motion`.
* Dependency-free SVG snapshots and optional PNG/GIF/MP4 export, including bundled
  FFmpeg for supported platforms. See :doc:`exports` for timing and memory limits.
* Explicit native terminal/audio diagnostic tooling and Linux/macOS PTY resize
  checks in CI. See :doc:`platform_checks`; hardware audio remains a manual check.

Upgrade notes
-------------

Audio now has seven curated modes, including full-screen ``objects``, ``tiles``
and ``glow``. Demo selection is manual through the arrow keys; it never auto-cycles.
Experimental audio modes/presets have been removed; this is a breaking API change.
See :doc:`bruheffect/audio_effect` for the complete removal list and replacements.
Fixed-scale levels, faster attacks, smoother releases, readable palettes and
device-rate frequency analysis replace the old per-chunk peak normalization.
Summed band energy retains diffuse treble, and less crowded bass spacing gives
mids and highs more screen space. The default noise floor is now -65 dB;
``AudioSettings(noise_floor=-55)`` restores the earlier display threshold.
The demo starts with Objects and explains each mode's response on screen.
Bars and Mirror use ``bar_gain=2`` for taller bars with moderate audio; use 1 to
restore their earlier height response. The multiplier affects only their display
and peak caps. Their demo configurations also fill the gaps between columns.
The audio demo now plays inside the original computer artwork with background
snow at 15 updates/sec. **C** cycles classic, expanded artwork, and a responsive
rectangular computer; small terminals use the rectangular frame automatically.
Expanded inserts center columns and monitor rows, preserving the original edges.
Audio fits the monitor's dimensions, including the original sloped screen, and
style changes preserve capture, snow, and mode selection.
The bouncing windows demo adds a fifth live-audio Panel (Mirror by default)
and enlarges the windows up to 60×20 cells, depending on the initial terminal size.
Its typed ``audio_mode`` selects the visualization; ``None`` retains four windows
without capture, as used by the existing rendering benchmarks.

Library playback keeps ``on_resize="raise"`` as its default; demos use
``"resize"``. When opting into resize, built-ins now grow their simulation areas
instead of revealing only the original raster. Cropped grid/raster cells are
discarded. Particle and audio policies are documented individually.

Image options and sequencing are additive. ``reverse=False`` preserves one-way
transition behavior. ``ImageEffect`` still paints plain spaces unless Layer
space transparency is enabled; transition glyphs use transparent spaces.
The generic Animation protocol remains the extension point for new content.

Native benchmark results depend on the terminal/backend and measure writes and
flushes, not final display latency. Audio resize tests use synthetic input;
native device support still depends on the optional audio backend.

Natural and procedural effects
------------------------------

Five new built-ins add Water, Smoke/Ink, Metaballs, Cloth/Flag, and Terrain.
The existing reaction-diffusion effect gains an organic preset with shaded
concentrations and scattered seeding; small seed regions now clip correctly.
Each addition includes validated typed settings/presets, seeded local randomness,
resize adapters, individual demos, and registry-driven CLI discovery.
Run ``python -m bruhanimate.demos.nature_demo`` to see all six in a reflowing gallery.
See :doc:`natural_effects` for controls, units, and simulation limits.

The new DiffusionSettings fields are keyword-only, preserving positional arguments.
DiffusionEffect.set_parameters now rejects invalid/nonfinite rates before mutation.
