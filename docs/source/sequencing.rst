Animation sequences
===================

``AnimationSequence`` schedules any Animation: image effects, labels, callbacks,
scenes, or a solver view. ``SequenceStep`` supplies a zero-argument factory, a
positive duration, an optional frozen hold, a blank gap, and a caption name.
All times are finite simulation seconds, independent of presentation FPS.
Both classes are exported from ``bruhanimate`` with typed constructors/properties.

.. code-block:: python

   from bruhanimate import (
       AnimationSequence, DissolveImageEffect, Layer, Scene, SequenceStep,
       TextStyle, WipeImageEffect, effect_registry, play,
   )

   def build(buffer):
       title = AnimationSequence(
           SequenceStep(
               lambda: WipeImageEffect("bruh", duration=1, direction="right"),
               duration=1, hold_duration=2, gap=0.5, name="Wipe",
           ),
           SequenceStep(
               lambda: DissolveImageEffect("bruh", duration=1, seed=42),
               duration=1, hold_duration=2, gap=0.5, name="Dissolve",
           ),
           repeat=True,
       )
       return Scene(
           Layer(effect_registry.create("plasma", buffer, " "), updates_per_second=30),
           Layer(title, style=TextStyle(foreground=231), preserve_background=True),
       )

   play(effect_factory=build, duration=12, fps=60, on_resize="resize")

For an entrance that reverses back out, configure ``reverse=True`` on the image
effect and give its step enough time for both legs and its internal hold. For
example, ``WipeImageEffect("bruh", duration=2, reverse=True, hold_duration=3)``
needs ``SequenceStep(..., duration=7, gap=1)``. A step's ``hold_duration`` freezes
the child's final frame after its entire duration; it is separate from a reversing
image's internal hold between legs. The :doc:`demos/tv_demo` demonstrates this.

Timing and skipped steps
------------------------

Only update advances time. Each child receives updates for at most its step
duration. When its optional ``finished`` property becomes True, further updates
stop; its final frame stays available through the remaining duration and hold.
The blank gap paints nothing, so a Scene reveals its lower layers cleanly.
``duration`` on the sequence includes all step durations, holds, and gaps.

Large time jumps go directly to the destination step. Skipped steps are never
constructed or updated. The destination receives one update with its elapsed
time; a fixed-tick simulation therefore performs one tick, not a replay of every
missed tick. Do not use skipped steps as callbacks for mandatory side effects.
Ordinary Player updates provide small intervals for continuous animation.

With ``repeat=False`` the sequence finishes at its total duration and retains
the last frame, or stays blank if the final step has a gap. ``repeat=True`` creates
fresh children on every entered cycle and never finishes. An empty sequence is
already finished. Use ``on_complete="hold"`` when a background should continue.

Ownership and resize
--------------------

Construction and draw do not call factories. start creates and starts the first
child; entering another step closes the old child before creating its replacement.
Each factory must return a fresh, unowned Animation. Never return the same object
on repeat, or share it with a Scene/Player. Cleanup covers partial startup failures;
close is idempotent and safe before start. A closed sequence cannot restart.

The sequence owns only its active child. ``current`` exposes a borrowed Animation
or None before start/after close; do not close it yourself. ``index``, ``phase_name``,
``visible``, and ``finished`` support captions and status displays. Configure steps
and repeat at construction. No terminal or input handling is created implicitly;
route keyboard events explicitly through Player if children need them.

``resize((width, height))`` preserves time and the active instance, forwarding the
notification to resizable content. Later children receive the latest size after
startup and before their first update/draw. Factories should construct inert
animations; children without a resize method must draw into arbitrary buffers.
Use :doc:`composition` to keep independent background animations running outside
the sequence, and :doc:`images` for transition options and masks.

API
---

.. automodule:: bruhanimate.sequence
   :members:
