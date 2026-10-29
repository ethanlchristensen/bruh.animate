Browsing, saved presets, and CLI export
=========================================

Browse live effects with the same Player and resize behavior used by Python:

.. code-block:: sh

   bruhanimate browse
   bruhanimate browse --seed 7
   bruhanimate browse --audio

Up/down changes effects; left/right changes presets. q, Escape, or Ctrl+C exits.
The selected Python command prints after the terminal is restored, ready to copy.
Application-defined effects must be registered before running the snippet.
Edited settings are constructed through the registry's settings type; the browser
does not guess imports for application classes or execute registration code.
Audio is excluded unless ``--audio`` is supplied; subprocess terminal effects are
excluded. Only one preview is owned at a time. Replacements close before the next
starts, selection is applied during update, and resizing retains current state.
The seed is reapplied when selecting a fresh preview, so comparisons are repeatable.

Press ``/`` to search names/descriptions and Enter to apply the filter; ``c``
cycles categories. Search can return zero results; press ``/`` again to change it.
Press ``e`` to edit a setting as ``FIELD=JSON`` (for example ``wind=0.6``).
Tab cycles fields, Ctrl+U clears the input, Enter applies, and Escape cancels.
Validated edits restart only the selected preview; invalid values leave it intact.
Boolean and tuple values use JSON, such as ``true`` or ``[1, 2, 3]``.

Press ``s`` to save resolved settings to ``preview-EFFECT-PRESET.json`` in the
current directory. Defaults use ``custom`` in the filename. ``--output-dir``
chooses an existing folder. Existing files are protected; save failures appear
in the browser status line. Press ``x`` to close the preview, restore the terminal,
then export an MP4 there with the same basename. ``--export-duration 5`` controls
the clip length in seconds. It recreates the selected settings/seed, rather than
recording the live screen. Audio previews cannot use this virtual-time export.

Ordinary effect startup, update and resize failures appear in the preview;
navigation remains available after successful child cleanup. Cleanup failures and
draw errors propagate to Player for terminal restoration. Ctrl+C is not swallowed.

Save and reuse settings
-------------------------

.. code-block:: sh

   bruhanimate save-preset snow snow.json --preset light --seed 42 --fps 60 --updates-per-second 30 --duration 5
   bruhanimate play snow --config snow.json
   bruhanimate play snow --config snow.json --set wind=0.4 --duration 10
   bruhanimate record snow snow.cast --config snow.json
   bruhanimate export snow snow.mp4 --config snow.json

Saved JSON contains resolved settings, rates, frame/duration limits and capture
dimensions. Rates use seconds; dimensions use terminal cells. A missing seed keeps
normal randomness. Explicit flags override saved options; ``--set`` overrides
individual saved settings; an explicit ``--preset`` replaces the saved settings
selection. ``--seed`` overrides the resulting seed. The effect argument must match
the file. Existing output requires ``--overwrite``; parent directories must exist.

Files use schema version 1 and are data only. Unknown names, fields, schema versions
and invalid settings fail before an effect starts. Custom effects must already be
registered and use dataclass settings to save/load. Named preset values are resolved
when saving, so later edits to the library's presets do not silently change the file.

.. code-block:: python

   from pathlib import Path
   from tempfile import TemporaryDirectory
   from bruhanimate import EffectConfig, effects

   config = EffectConfig("snow", effects.snow.preset("light"), duration=5)
   with TemporaryDirectory() as directory:
       path = config.save(Path(directory) / "snow.json")
       restored = EffectConfig.load(path)
       assert restored.settings == config.settings

GIF/MP4 from the command line
-------------------------------

Install ``bruhanimate[export]`` first. Capture uses virtual time and requires a finite
``--frames`` or ``--duration`` bound, directly or from a saved file. No terminal is
opened. Output format follows the .gif/.mp4 suffix; errors preserve existing output.

.. code-block:: sh

   bruhanimate export plasma plasma.mp4 --duration 5 --width 80 --height 24
   bruhanimate export fire fire.gif --frames 60 --fps 20 --width 30 --height 12
   bruhanimate export snow snow.mp4 --duration 5 --font path/to/mono.ttf --font-size 18 --cell-width 12 --cell-height 22

GIF memory limits, MP4 encoding, color/font support and ownership match the
:doc:`exports` API. Live audio/worker sources are not deterministic virtual-time
sources; use reproducible snapshots for offline export.

API
-----

.. automodule:: bruhanimate.config
   :members:

.. automodule:: bruhanimate.browser
   :members:

Setup diagnostics
------------------

Run ``bruhanimate doctor`` for a readable setup report, or ``bruhanimate doctor
--json`` for machine-readable output. It reports Python and package versions,
stdout terminal/encoding information, color environment hints, and availability
of optional export and audio modules, with install commands for missing tools.
It does not open a terminal, enumerate audio devices, start workers or run FFmpeg.
Detected modules and environment hints do not establish actual hardware support.

.. code-block:: python

   from bruhanimate.doctor import diagnose

   report = diagnose()
   assert "available" in report and "limits" in report
