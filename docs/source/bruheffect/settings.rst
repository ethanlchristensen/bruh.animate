Settings
========

Most built-in effects are configured through a settings dataclass. Construct
a settings object, populate only the fields you care about (all have defaults), and
pass it to the effect constructor. Settings can also be omitted entirely — each
effect falls back to its own defaults.

.. code-block:: python

   from bruhanimate import SnowSettings, effects

   effects.snow.play(settings=SnowSettings(wind=0.6), duration=10)

Settings validate types and finite values on construction and again when passed
to an effect. Ranges and choices are available through ``bruhanimate info EFFECT``.
Invalid types raise TypeError; invalid values raise ValueError with the field
name. Zero probability disables new particles where supported, and palette index
0 means black. See :doc:`../discovery` for presets, editor hints, and CLI usage.

.. automodule:: bruhanimate.bruheffect.settings
   :members:
   :undoc-members:
   :show-inheritance:
