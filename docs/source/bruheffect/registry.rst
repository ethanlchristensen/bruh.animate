Effect Registry
===============

The ``effect_registry`` is a module-level singleton that maps every built-in effect
name to its implementation class, settings class, description, and named presets.
It is the single source of truth used by the player and CLI to instantiate
effects, and is fully open for extension with your own custom effects.

See :doc:`../discovery` for the typed ``effects.snow`` catalog, preset inspection,
CLI commands, and settings validation. ``presets(name)`` returns independent
settings copies. ``resolve_settings`` validates selections without constructing
effects. Explicit settings override a known preset; unknown presets always fail.

.. code-block:: python

   from bruhanimate import effect_registry

   # Discover all registered effects
   for name, entry in effect_registry.entries().items():
       print(name, "—", entry.description)

   # List presets for an effect
   print(effect_registry.presets("snow"))
   # {'light': SnowSettings(...), 'blizzard': SnowSettings(...), ...}

   # Create an effect instance by name using a preset
   effect = effect_registry.create("snow", buffer, " ", preset="blizzard")

   # Create with a custom settings object (takes priority over preset)
   from bruhanimate import SnowSettings
   effect = effect_registry.create("snow", buffer, " ", settings=SnowSettings(wind=0.9))

   # Register your own effect
   effect_registry.register(
       "myeffect",
       MyEffect,
       settings_cls=MySettings,
       description="Does something cool",
       presets={"fast": MySettings(speed=10)},
   )

.. automodule:: bruhanimate.bruheffect.registry
   :members:
   :undoc-members:
   :show-inheritance:
