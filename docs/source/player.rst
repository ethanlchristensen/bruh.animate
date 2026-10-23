Player and composition
======================

Use one player for simulations, drawing callbacks, and layered scenes.

.. code-block:: python

   from bruhanimate import ImageEffect, Scene, effect_registry, play

   def build(buffer):
       snow = effect_registry.create("snow", buffer, " ", preset="light")
       return Scene(snow, ImageEffect("Hello!"))

   play(effect_factory=build, fps=60, updates_per_second=30)

The factory receives a screen-sized Buffer. Named effects can be played directly
with settings or a preset. Player(screen, animation) borrows an existing Screen;
play opens/restores its own. Both return the number of presented frames.

Animation contract
------------------

* start acquires resources; construction must be inert.
* update(dt) advances simulation; dt is seconds.
* draw(buffer) reads current state without advancing or consuming solver input.
* close releases resources and must be safe before startup and on repeats.

BaseEffect requires update and supplies a draw implementation for its persistent
private raster. CallbackEffect accepts explicit draw and optional update functions.
Player registers cleanup before startup; Scene closes started children in reverse
order, including partial startup failure. Do not share one instance across owners.

Timing and composition
----------------------

FPS controls presentations. An explicit updates_per_second schedules fixed ticks,
independent of FPS, with bounded catch-up. Without it, update runs once per draw.
Built-ins advance once per tick; their probabilities and speed settings use ticks.
frames counts presentations, and None runs until quit. fps=None disables pacing.

Scene paints children from back to front. None is transparent; spaces paint unless
Layer(animation, transparent=True) opts into space transparency. ImageEffect
centers text/image rows by default, accepts x/y including zero/negative positions,
and moves at velocity=(columns_per_second, rows_per_second). Content clips.

Default quit keys are q/Q, Escape, and Ctrl+C. Player's event_handler replaces
this routing; True means quit. play also accepts an event_handler. Pass TerminalEffect.handle_event for shell input.
Resize raises ScreenResizedError after cleanup; other errors also propagate.
manage_effect=False borrows an already started instance without start/close.

See the `full player guide
<https://github.com/FNBBDevs/bruhanimate/blob/main/docs/PLAYER.md>`_
for lifecycle, buffer ownership, transparency, and limitations.

on_complete="hold" keeps presenting completed content; "exit" stops after the
final draw. Playback exposes a finished flag, and Scene completes when all finite
children complete while ignoring endless backgrounds. See :doc:`playback` and
:doc:`grid` for solver controls and board drawing.

API
---

.. automodule:: bruhanimate.player
   :members:

.. automodule:: bruhanimate.scene
   :members:
