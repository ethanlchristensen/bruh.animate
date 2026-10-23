Solver playback
===============

Playback consumes a lazy iterator of snapshots only during update. Drawing reads
the current snapshot. Pass its handle_event explicitly to enable pause/step/speed
controls. The source should yield immutable snapshots or use copy_state=deepcopy.

.. code-block:: python

   from bruhanimate import Playback, draw_grid, play

   board = ("S...", ".##.", "...E")

   def states():
       yield from ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2))

   def draw(position, buffer):
       grid = draw_grid(buffer, board, spacing=(2, 1))
       grid.put(*position, "@")

   animation = Playback(states(), draw, steps_per_second=5)
   play(animation, event_handler=animation.handle_event, on_complete="exit")

Space/p pauses, n/right-arrow steps, +/- changes speed, and q/Escape quits. Pausing
the solver does not pause other scene children. Playback stores one snapshot and
closes its owned iterator on exhaustion or early cleanup. It is single-use.
Solver work runs synchronously; each next() must perform bounded work to keep
input responsive. Sample or aggregate large searches within the producer.

on_complete="hold" keeps polling input over the final state; "exit" stops after
presenting completed content. Exhaustion is detected on the next scheduled source
advance, without lookahead. Scene completes when all finite children complete,
ignoring endless backgrounds. Empty sources present one background frame.

Run ``python -m bruhanimate.demos.grid_demo`` for a pure BFS solver, clipped maze
drawing, background animation, controls, and final path. See the `full guide
<https://github.com/FNBBDevs/bruhanimate/blob/main/docs/SOLVER_PLAYBACK.md>`_
for snapshots, ownership, timing, sampling, and completion details.

.. automodule:: bruhanimate.playback
   :members:
