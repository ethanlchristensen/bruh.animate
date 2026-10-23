Dashboard demo
==============

A dashboard built with Row, Column, Label, StatusBar, and Panel. Run it in your
normal terminal, including Windows Terminal:

.. code-block:: shell

   python -m bruhanimate.demos.dashboard_demo

.. code-block:: python

   from bruhanimate import dashboard_demo

   dashboard_demo.run(frames=360, fps=60)

The layout contains a one-row title, a flexible beam-solver panel with an activity
log below it, a 24-column statistics sidebar, and a one-row status bar. Snow animates behind the solver
at 15 updates/sec; a small plasma preview updates at 30/sec. The public beam
fixture advances at two steps/sec, and Player presents at 60 FPS by default.
The final board stays visible until quit or the frame limit.

Tab/Shift+Tab moves focus through solver, signal, and log panels. The selected
border is bold yellow, and the status bar shows its declared bindings:

* **Solver:** Space pauses/resumes, n queues one step, +/- changes speed.
  Arrows, Page Up/Down, Home/End pan the full board through its ScrollView.
* **Signal:** Space pauses/resumes plasma, r remixes its pattern.
* **Log:** Arrows, Page Up/Down, Home/End browse activity. Upward scrolling/Home
  suspends automatic scrolling; End resumes following. The status bar shows
  ``log LIVE`` or ``log HISTORY``.
* **Anywhere:** q/Q, Escape, or Ctrl+C quits.

Space affects only the selected panel; snow keeps advancing. The statistics
sidebar shows both focus and signal pause state. Text callbacks read playback state
during updates, not drawing. The solver updates before its statistics labels.
All puzzle rules remain in demo code; the fixture is independently created and
requires no private puzzle inputs or external tools.

The LogView retains 200 logical lines and wraps at cell boundaries. It records
solver step requests/progress/completion, pause/resume, speed changes, and signal
remixes. Progress is observed once after each scene update; drawing never appends
messages or consumes snapshots. New messages preserve your reading position while
browsing; if that line is evicted, the oldest remaining line becomes visible.
The views are ordinary owned children in the layout and close even when their
slots never become visible.

An 80-column by 24-row terminal displays the full dashboard. Smaller terminals
shrink the flexible area first. Live resize is enabled by default: pause with
Space while the solver is selected, resize smaller and larger, then select the
solver and press n to advance exactly one snapshot.
The current board, step count, speed, queued input and iterator remain intact.
The solver's full canvas stays the same size while its viewport changes. LogView
rewraps retained text, keeping the top logical line/character where possible or
following the tail when enabled.
Existing children continue updating while hidden; initially hidden factories wait
until first visible allocation. Snow fills the new background area and anchors
its floor pile to the new bottom; plasma fills its panel without restarting its
phase. A hidden panel is skipped during focus navigation; if the selected panel
becomes hidden, focus moves to the next available target. Making it visible again
does not steal focus. Cropped snow is discarded, while visible flakes keep their drift and fall
delay. Pass
``run(on_resize="raise")`` for the compatibility behavior. See :doc:`../resize`.
Edit
``build_scene`` to change Fixed/Flex sizing, gaps, typed TextStyle settings, or
the effects. ``DashboardControls`` builds typed bindings; ``build_scene`` attaches
its targets to panels, and ``run`` passes its FocusGroup handler to Player.
No action runs from drawing. See :doc:`../layouts`, :doc:`../views`, and :doc:`../keyboard` for the
public APIs and lifecycle rules.

.. automodule:: bruhanimate.demos.dashboard_demo
   :members:
