Solver history and background work
====================================

Ordinary Playback keeps one snapshot and executes the source synchronously. These
two opt-in classes retain the same update/draw/close and explicit input-routing
contracts while adding different capabilities. They do not change Playback's defaults.

Bounded recent history
------------------------

.. code-block:: python

   from bruhanimate import HistoryPlayback, play

   def draw(state, buffer):
       buffer.put_at(0, 0, f"Step {state}")

   animation = HistoryPlayback(range(100), draw, capacity=20, steps_per_second=5)
   play(animation, event_handler=animation.handle_event, frames=120)

Left arrow/b queues one backward step and pauses. Existing Space/p, n/right,
+/-, and quit controls work as in Playback. ``seek(index)`` queues a zero-based
source index within the retained window. ``position`` is the displayed index;
``steps`` is the total source snapshots consumed. Forward playback reuses retained
states before requesting new ones, including after source exhaustion. Drawing
never consumes or navigates. Use ``on_complete="hold"`` to explore a completed run.

``bookmark(name)`` records the displayed index. ``bookmarks`` returns an independent
name-to-index mapping; pass an index to ``seek``. Eviction drops bookmarks referring
to evicted states. Capacity counts snapshots, not bytes, and defaults to 100. States
must be immutable or supplied with ``copy_state=deepcopy``. The source is lazy and
its iterator closes on exhaustion/early quit. This is recent history, not random
access to arbitrary future or evicted snapshots.

Cooperative background sources
--------------------------------

.. code-block:: python

   from bruhanimate import BackgroundPlayback, play

   def states(cancel):
       for index in range(100):
           if cancel.wait(0.02):
               return
           yield index

   def draw(state, buffer):
       buffer.put_at(0, 0, str(state))

   animation = BackgroundPlayback(states, draw, capacity=4)
   play(animation, event_handler=animation.handle_event, frames=120)

The factory receives a threading.Event and runs only after start, on one worker.
The worker acquires/closes its iterator; UI callbacks run only on Player's thread.
Use immutable snapshots or ``copy_state`` to copy on the worker before enqueueing.
Capacity bounds queued snapshots (default eight), with at most one more in flight.
Pausing may let the queue fill, then backpressure stops production. Empty queues
retain the displayed frame; manual steps wait for actual snapshots. Worker errors
propagate during update after earlier queued states, and completion follows the
worker's exhaustion marker. Input is passed explicitly to ``handle_event``.

Factories must check cancellation and bound blocking work/I/O. Python cannot kill
an arbitrary blocked thread. Close signals cancellation and joins for
``close_timeout`` seconds (default one); a stuck worker raises RuntimeError and a
later close can retry the join. Start/close failures still follow Player ownership.
This improves responsiveness, not CPU parallelism. Use a process-based producer
in application code when CPU isolation is needed.

Live worker timing is unsuitable for deterministic virtual-time capture/export;
first produce a recording or deterministic snapshots. BackgroundPlayback and
HistoryPlayback are separate options; a combined background/history controller
is not provided by these classes.

API
-----

.. automodule:: bruhanimate.history
   :members:

.. automodule:: bruhanimate.background
   :members:
