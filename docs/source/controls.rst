Animation timing and queued actions
============================================

``AnimationControl`` owns one animation and adds pause/resume, single-step and
time scaling. ``ActionQueue`` holds bounded application commands for explicit
consumption during updates. Neither creates a playback loop, polls a terminal,
or infers the timing model of a child.

Choose a timing mode
--------------------------------------------

Use ``mode="fixed"`` for built-in effects that advance one simulation tick per
update call. The control accumulates scaled seconds and calls its child with
``step_seconds`` (default 1/30 second) for each due tick. Half speed means fewer
updates, rather than calling a tick-based simulation with a smaller dt.

.. code-block:: python

   from bruhanimate import AnimationControl, Buffer, SnowEffect, SnowSettings, capture

   snow = SnowEffect(Buffer(8, 30), " ", SnowSettings(seed=7, intensity=0.1))
   control = AnimationControl(snow, mode="fixed", time_scale=0.5)
   frames = []
   capture(control, width=30, height=8, frames=2, on_frame=frames.append)
   assert frames

Use ``mode="continuous"`` only for children documented to integrate elapsed
seconds, such as Sprite or Tween. It forwards one ``dt * time_scale`` per parent
update. Wrapping a tick-based effect in continuous mode cannot slow its tick
count. Mixed content can use separate controls for different children, or a
fixed-mode control with a deliberate tick interval for the entire composition.

.. code-block:: python

   from bruhanimate import AnimationControl, Sprite, SpriteAsset

   sprite = Sprite(SpriteAsset.from_text("@"), velocity=(6, 0))
   control = AnimationControl(sprite, mode="continuous", time_scale=0.5)
   control.start()
   try:
       control.update(2)
       assert sprite.position == (6, 0)
   finally:
       control.close()

Timing mode and step interval are fixed at construction. Time scale can change
at runtime and must be finite and non-negative. Zero scale sends no child
updates. Zero incoming dt also sends no automatic update. A scaled product that
overflows raises before changing the clock or child. Floating-point underflow
to zero produces no child update.

Fixed mode shares the existing Scene/Layer scheduling policy: at most
``max_catch_up`` child updates per parent update (default five). Reaching that
cap drops the entire accumulator, including its fractional remainder. Below
the cap, fractional time is retained. Large updates therefore do not imply
unbounded catch-up or exact offline elapsed-time equivalence. Use sufficiently
small parent ticks for deterministic full-speed offline simulation. Avoid adding
another Layer tick scheduler around the control unless both cadences are intended.

Pause, manual step and completion
--------------------------------------------

.. code-block:: python

   from bruhanimate import AnimationControl, Sprite, SpriteAsset

   sprite = Sprite(SpriteAsset.from_text("X"), velocity=(4, 0))
   control = AnimationControl(
       sprite, mode="continuous", paused=True, step_seconds=0.25,
   )
   control.start()
   try:
       control.update(100)
       assert sprite.position == (0, 0)
       control.step()        # requests work, does not update the sprite yet
       control.step()        # coalesces with the pending request
       control.update(0)     # one manual step, even with zero parent dt
       assert sprite.position == (1, 0)
       control.resume()
       control.update(0.5)
       assert sprite.position == (3, 0)
   finally:
       control.close()

``pause`` suppresses child updates completely; it does not forward ``update(0)``.
Draw still paints the child's current state. ``step`` requires a paused, open
control and schedules one ``step_seconds`` update on the next parent update,
ignoring time scale even if it is zero. Repeated requests coalesce until consumed.
``resume`` cancels an unconsumed manual step. ``toggle_pause`` is a convenience
action for a KeyBinding. Pause, stepping, resize and scale changes preserve the
existing fractional fixed-step accumulator. Time spent paused is never replayed.

Completion mirrors the child's ``finished`` value. A finished child continues
to draw but receives no additional automatic or manual updates. Completion,
pause or setting scale to zero during a fixed catch-up batch prevents the
remaining scheduled ticks; their time is discarded while any fractional
remainder survives. Other scale changes inside a child update apply on the next
parent update. Ordinary update/draw exceptions
propagate to the owner, normally Player, which performs cleanup.

The wrapper owns its child from construction, closes it even before start or
after a startup failure, and cannot restart after close. Close is idempotent,
including when child cleanup raises. Repeated start does not reset state.
Resize and visibility notifications forward to the child without advancing it.
Pause does not hide a child or disable its input: controls do not forward input
automatically. Route input explicitly through Player/FocusGroup and put pause
menus outside the paused subtree. When using CachedAnimation, retain its explicit
invalidation responsibilities; controls do not invalidate drawing caches.

Apply actions during updates
--------------------------------------------

.. code-block:: python

   from bruhanimate import ActionQueue, KeyBinding, KeyBindings

   actions = ActionQueue[str](capacity=8)
   keys = KeyBindings(
       KeyBinding("left", actions.bind("west")),
       KeyBinding("right", actions.bind("east")),
       KeyBinding.character("q", quit=True),
   )
   assert not keys.handle_event(-203)
   assert actions.drain(limit=1) == ("west",)
   assert actions.drain() == ()

``push(action)`` returns True if accepted and False if full, dropping the newly
submitted value. ``bind(action)`` creates a zero-argument, None-returning callback
that works with KeyBinding; it discards that acceptance result. Bind does not
enqueue immediately. Use push directly when overflow needs visible feedback.
Capacity is a positive integer; limit is non-negative and defaults to one.

``drain`` removes a bounded batch and returns a detached tuple. Process it in
application update code. Commands queued by that processing remain pending for
a later drain. ``clear`` discards pending commands; neither operation executes
payloads. Values are borrowed rather than copied: immutable strings, tuples or
frozen records are useful when recording input for replay. The queue has no
clock, automatic tick assignment, persistence or history, and is for use on the
playback thread, not communication with worker threads. Calling drain more than
once per update is an explicit application choice.

The :doc:`topdown` demo now uses ActionQueue for its existing 16-command queue.
Applying recorded commands at the same update indices still reproduces world
state; presentation FPS and wall-clock event arrival alone do not define a replay.

Interactive demo
--------------------------------------------

Run ``python -m bruhanimate.demos.controls_demo`` for fixed-tick snow and a
continuous moving sprite. Space pauses/resumes both; N pauses and requests one
step; 1/2/3 select half/normal/double speed; 0 freezes time scale; Q quits.
Input commands apply during updates through a bounded ActionQueue. The player
continues polling and painting while its children are paused. The HUD remains
outside the controlled content, and resize retains simulation progress.

API
--------------------------------------------

.. autoclass:: bruhanimate.AnimationControl
   :members:

.. autoclass:: bruhanimate.ActionQueue
   :members:
