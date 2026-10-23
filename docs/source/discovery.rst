Discover effects, presets, and settings
=======================================

The same typed catalog exposes ``capture`` and ``record`` methods with matching
preset/settings hints. See :doc:`capture` for seeded randomness, immutable frame
snapshots, and headless ``.cast`` export. ``bruhanimate info EFFECT`` includes
the inherited ``seed`` setting; ``play`` and ``record`` also accept ``--seed``.

A preset is a named settings object. For example, snow's ``light`` preset uses
``SnowSettings(intensity=0.005, wind=0.0, show_info=False, collision=False)``.
It lowers the per-column, per-tick chance of creating a flake from the default
0.01 to 0.005. It does not change playback FPS or simulation tick frequency.

Explore in Python
-----------------

.. code-block:: python

   from bruhanimate import effects

   print(effects.names())                 # All registered effects, including extensions
   print(effects.snow.description)
   print(effects.snow.defaults())         # A fresh SnowSettings object
   print(effects.snow.presets())          # light, moderate, blizzard, windy + values
   print(effects.snow.preset("light"))     # One independent SnowSettings copy

Type ``effects.`` in an editor to browse the built-in catalog. Its members are
statically declared, so editors can discover them without running animations.
``effects.snow.play(preset=...)`` and ``effects.snow.preset(...)`` use snow-specific
Literal types; compatible editors suggest its preset names. Settings parameters
and return values retain the concrete settings class. Exact completion UI depends
on your editor and Python language server.

.. code-block:: python

   from bruhanimate import effects

   effects.snow.play(preset="light", fps=60, updates_per_second=30, duration=10)

The string-based API remains available and accepts custom registered names:

.. code-block:: python

   from bruhanimate import play

   play("snow", preset="light", fps=60, updates_per_second=30, duration=10)

The general ``play`` function accepts arbitrary registry names and validates
their settings/presets at runtime. Use the typed catalog for effect-specific
static checks. ``EffectName`` describes built-in names only; it does not limit
runtime registration. ``effect_registry.names()``, ``get(name)``, and
``presets(name)`` also support custom effects. Static catalog members are not
generated dynamically for extensions or registry replacements.

Customize a preset
------------------

.. code-block:: python

   from bruhanimate import effects

   settings = effects.snow.preset("light")
   settings.wind = 0.4
   effects.snow.play(settings=settings, duration=10)

Preset inspection returns independent copies, including nested lists. Editing
one cannot alter future animations. Explicit settings replace a preset's whole
configuration; they are not a partial merge. When both settings and a preset are
supplied, the preset name must still exist. Settings objects remain mutable, but
editing one does not reconfigure a running effect.

Built-in dataclasses validate at construction, and built-in effects validate
again before using supplied settings. Wrong types raise ``TypeError``; invalid
ranges, choices, non-finite numbers, and unsupported glyphs raise ``ValueError``
with the field name. Booleans are not numbers. Glyph fields accept one printable
single-cell character; wide/combining characters and escape sequences are not
supported. Valid zero values and ANSI color index 0 are preserved.

Custom registry settings are checked against their declared class. They can
inherit ``EffectSettings`` to opt into built-in field validation, or enforce
their own rules. Existing individual effect setter methods retain their
documented behavior; these validation rules apply to settings objects.

Explore from the command line
-----------------------------

Both entry points use the same registry and player:

.. code-block:: sh

   bruhanimate list
   bruhanimate presets snow
   bruhanimate info snow
   bruhanimate play snow --preset light --duration 10 --fps 60 --updates-per-second 30
   python -m bruhanimate info snow

``list`` shows descriptions; ``presets`` shows names and complete configurations;
``info`` additionally shows field types, defaults, and numeric ranges. Discovery
does not construct effects, open a terminal, or start audio capture. Use
``bruhanimate --help`` and ``bruhanimate play --help`` for command options.
In a source checkout, prefix commands with ``uv run --locked``.

Override individual fields with repeatable ``--set FIELD=VALUE`` arguments.
Overrides are applied to the chosen preset, or to defaults when no preset is
selected. Values are JSON (numbers, ``true``/``false``, arrays, ``null``), or text
for choices such as ``east``. Quote values as required by your shell:

.. code-block:: sh

   bruhanimate play snow --preset light --set wind=0.4 --duration 10
   bruhanimate play matrix --set 'character_halt_range=[2,4]' --duration 10
   bruhanimate play rain --set wind_direction=east --set lightning_color_type=0

Invalid names, settings, and timing options fail before opening a terminal.
``--duration`` is wall-clock seconds after startup, including paused or held
time. ``--frames`` limits presentations. The first limit or quit request wins;
zero starts no effect. Synchronous work cannot be interrupted mid-callback, so
a slow callback may overrun a duration. ``play`` still opens/restores its Screen
for zero-duration playback. See :doc:`player` for lifecycle details.

Catalog API
-----------

.. autoclass:: bruhanimate.effects.EffectInfo
   :members:

.. autofunction:: bruhanimate.effects.names

.. autofunction:: bruhanimate.effects.get
