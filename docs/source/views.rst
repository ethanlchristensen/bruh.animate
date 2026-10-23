Scrollable views and activity logs
====================================

``ScrollView`` displays part of an animation's larger canvas. ``LogView`` retains
recent text and follows new messages until you scroll upward. Both are animations
with typed options, viewport resize support, and reusable ``KeyBindings``. They
use the existing Player loop and require no new dependencies.

A focused activity log
------------------------------------

.. code-block:: python

   from bruhanimate import (
       Column, Fixed, FocusGroup, FocusTarget, KeyBinding, KeyBindings,
       LogView, Panel, Slot, StatusBar, TextStyle, play,
   )

   log = LogView(size=(40, 6), max_lines=200, wrap="character",
                 style=TextStyle(foreground=252, background=235))
   log.append("Ready. Press a to append a message.\nUse arrows to browse history.")
   state = {"count": 0}

   def add_message() -> None:
       state["count"] += 1
       log.append(f"Message {state['count']}")

   target = FocusTarget("activity", KeyBindings(
       *log.bindings.bindings,
       KeyBinding.character("a", add_message, description="append"),
   ))
   focus = FocusGroup(target)
   layout = Column(
       Slot(Panel(log, size=(40, 6), fit=True, title="Activity", focus=target)),
       Slot(StatusBar(lambda: "LIVE" if log.follow_tail else "HISTORY",
                      center=focus.help_text, right="q quit"), size=Fixed(1)),
   )
   play(effect_factory=layout.build, event_handler=focus.handle_event,
        on_resize="resize", frames=180)

The panel owns the log. Call ``append(text)`` before startup or from an input
action/simulation update. It changes history immediately; draw only paints the
retained text. Do not append from draw or from Label/StatusBar callbacks. Background
workers should queue messages for application code to drain during update; the
widget is not a thread-safe logging handler and does not poll external sources.

Log options and retention
------------------------------------

* ``size=(width, height)`` is the positive viewport size in cells. Layouts and
  fitting panels send resize notifications. When used directly, provide the
  initial size, or construct the view in a factory from its allocated Buffer.
* ``max_lines=1000`` is a positive logical-line limit. Newline-separated text adds
  multiple lines; an empty string adds one blank line, and a trailing newline
  adds a final empty line. The oldest excess lines are discarded.
* ``wrap="character"`` breaks long lines at cell boundaries, matching Label's
  wrapping behavior. ``wrap="none"`` keeps logical lines intact and enables
  horizontal scrolling. The exported ``LogWrap`` Literal exposes both choices.
* ``follow_tail=True`` starts at the newest messages. It is a mutable Boolean
  property; setting it True immediately returns to the bottom.
* ``style=TextStyle(...)`` applies ANSI styling per cell. Text itself must contain
  plain single-cell characters and optional newlines. Tabs, inline escape codes,
  and wide/combining glyphs are rejected before history changes.
* ``fill=True`` paints styled spaces across the viewport; False leaves unused
  cells untouched. Spaces within a message still paint.

``lines`` is an immutable tuple snapshot of retained logical lines. ``line_count``,
``max_lines``, ``wrap``, ``offset``, ``size``, ``content_size``, and ``at_bottom``
are typed read-only properties. ``clear()`` empties history and resets both
offsets while retaining the current follow setting.

The limit counts logical lines, not wrapped rows or characters. A very long
message still occupies memory proportional to its length; choose a message-size
limit in application code if needed. LogView indexes wrapped rows without building
a full character canvas for the entire history.

Following and preserving your place
------------------------------------

Up/Page Up or any upward ``scroll_to``/``scroll_by`` request suspends following,
even when already at the top. Home also suspends it. New messages then preserve
the top visible logical line and its character position. When that line is
evicted, the view shows the oldest retained line. Scrolling down to the bottom
does not resume following automatically: press End or set ``follow_tail=True``.
Horizontal scrolling leaves the follow setting unchanged.

Resize rewraps text. While browsing history, the new top row contains the character
that was at the start of the old top row, subject to bottom clamping. While
following, resize keeps the newest row visible. Empty logs and content smaller
than the viewport have zero offsets. Draw never modifies offsets or follow state.

A larger animation canvas
------------------------------------

.. code-block:: python

   from bruhanimate import (
       FocusGroup, FocusTarget, Label, Panel, ScrollView, play,
   )

   text = "\n".join(f"Row {row:02}: " + "0123456789" * 8 for row in range(60))
   view = ScrollView(Label(text), size=(38, 8), content_size=(88, 60))
   focus = FocusTarget("document", view.bindings)
   group = FocusGroup(focus)
   panel = Panel(view, size=(38, 8), title="Scrollable document", focus=focus, fit=True)
   play(panel, event_handler=group.handle_event, on_resize="resize", frames=180)

ScrollView owns exactly one supplied Animation. ``content_size`` is the positive
full canvas size; ``size`` is the visible viewport. At startup the child receives
a resize notification for the content dimensions, then starts once. Child updates
receive the parent's simulation seconds. Its optional ``finished`` status passes
through unchanged, so wrapping Playback preserves finite completion.

``resize((width, height))`` changes the viewport only. It keeps the child, solver
iterator, queued steps, and simulation state alive, clamping the offset when
necessary. ``set_content_size((width, height))`` explicitly changes the full canvas
and notifies an already started child without restarting it. The child controls
how it adapts to that notification. A viewport resize never changes the canvas.

The canvas is a rectangular Buffer, so memory and child drawing cost scale with
``content_size``. This is suitable for modest boards and documents; LogView avoids
allocating such a canvas for long histories. Construct built-ins with a matching
content-sized buffer. ``background=" "`` fills empty cells; None reveals lower
layers through transparent content. Plain child spaces paint.

Shared navigation and lifecycle
------------------------------------

``view.bindings`` provides arrows, Page Up/Down, Home, and End. Pass it to a
FocusTarget attached to the containing Panel. The FocusGroup handles navigation
and default quit keys; only the selected target receives scrolling keys. The
view's bindings by themselves install no quit keys. Extend them with
``KeyBindings(*view.bindings.bindings, ...)``; duplicate keys are errors.

The typed programmatic methods use cell coordinates:

* ``scroll_to((x, y))`` selects an absolute column/display-row offset.
* ``scroll_by(dx=0, dy=0)`` moves by signed columns/rows; positive means right/down.
* ``page_up()`` / ``page_down()`` moves one viewport height with one row of overlap
  where possible (one row minimum).
* ``home()`` moves to the top-left. ``end()`` moves to the bottom, retaining the
  horizontal offset; on LogView it also resumes following.

All offsets clamp to content bounds. Scrolling never advances simulation or
consumes solver snapshots. Constructors are inert; scrolling and appending may
be configured before start. Update/draw require successful startup. Close is
idempotent and views are single-use after close. ScrollView closes its child even
if never started or if startup fails; never share that child with another owner.
LogView owns no external resources. Neither view polls input or opens a terminal.

Layouts remove zero-area slots from focus while already started children keep
updating. Use a FocusTarget on the enclosing panel for viewport navigation;
scrolling does not perform hit-testing for focusable descendants inside a canvas.
See :doc:`keyboard`, :doc:`resize`, and the :doc:`demos/dashboard_demo`.

API
------------------------------------

.. automodule:: bruhanimate.views
   :members:
   :inherited-members:
