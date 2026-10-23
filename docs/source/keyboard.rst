Keyboard bindings and focus
===========================

``KeyBinding`` describes an action, ``KeyBindings`` groups actions, and
``FocusGroup`` routes input to a selected panel. Player remains the only input
poller. These helpers do not open a terminal, start threads, or own animations.

An interactive panel
--------------------

.. code-block:: python

   from bruhanimate import (
       Column, Fixed, FocusGroup, FocusTarget, KeyBinding, KeyBindings,
       Label, Panel, Slot, StatusBar, play,
   )

   state = {"count": 0}

   def increment() -> None:
       state["count"] += 1

   counter = FocusTarget("counter", KeyBindings(
       KeyBinding("space", increment, description="increment"),
       KeyBinding("enter", increment),  # Alias omitted from the help text.
   ))
   focus = FocusGroup(counter)
   layout = Column(
       Slot(Panel(Label(lambda: f"Count: {state['count']}"),
                  size=(20, 3), fit=True, title="Counter", focus=counter)),
       Slot(StatusBar("counter", center=focus.help_text, right="q quit"), size=Fixed(1)),
   )
   play(effect_factory=layout.build, event_handler=focus.handle_event,
        on_resize="resize", frames=180)

Attach a separate FocusTarget to each interactive Panel and list targets in the
FocusGroup's desired navigation order. Tab selects the next available target;
Shift+Tab selects the previous one. Navigation wraps by default. A focused panel
has a bold border with ANSI palette color 226; choose
``Panel(focus_border_color=117, ...)`` or None to retain its normal border color.
Borderless panels still receive focus; use ``target.focused`` in a label callback
to show selection. Drawing never changes focus or invokes bindings.

Discovering keys and actions
------------------------------

Typing ``KeyBinding("`` in an editor exposes the ``KeyName`` Literal choices:

* ``space``, ``enter``, ``escape``, ``tab``, ``shift+tab``, ``backspace``
* ``left``, ``right``, ``up``, ``down``, ``home``, ``end``, ``page_up``, ``page_down``
* ``insert``, ``delete``, ``ctrl+c``, and ``f1`` through ``f12``

Use ``KeyBinding.character("n", action, description="step")`` for a printable
single-cell character. Character bindings are case-sensitive. ASCII characters
are the portable choice; terminal encoding and key interception can limit which
events reach the application. Arbitrary modifier chords and text editing are not
provided. Wide/combining glyphs, control characters, and escape sequences are not
valid character bindings.

Actions take no arguments and return None. A matching action consumes its key;
``quit=True`` explicitly requests exit after an optional action. Duplicate keys
within one KeyBindings are rejected, including named ``space`` and character
``" "``. Different targets may bind the same key to different actions.

``bindings.hints()`` returns typed, immutable ``BindingHint(key, description)``
records in declaration order. ``bindings.help_text(separator=" | ")`` formats
them. Empty descriptions omit aliases from help. ``focus.help_text`` is a
zero-argument callback returning the selected target's help, suitable for
StatusBar. It excludes navigation and global bindings, which can be displayed
separately. Label/status callbacks refresh on updates, so hints refresh on the
next update after input.

Routing and explicit quit
-------------------------

FocusGroup processes each event once, in this order:

1. Reserved navigation keys move focus and consume the event.
2. The focused target's bindings get the event.
3. If unhandled, application-wide bindings get the event.

By default, unhandled q/Q, Escape, and Ctrl+C request quit, including when no
target is available. A local binding can consume those keys first. Supplying
``global_bindings=KeyBindings(...)`` replaces all those defaults; include your
own quit binding. ``next_key="down"``, ``previous_key="up"``, and ``wrap=False``
are typed options for alternative navigation. Reserved keys take priority over
local and global bindings.

``focus.focus("counter")`` selects an available named target and returns True;
it returns False for an unavailable target and raises KeyError for an unknown
name. ``focus.move("next")`` / ``focus.move("previous")`` expose the same
navigation with the public ``FocusDirection`` Literal type.

Use ``event_handler=focus.handle_event`` or ``bindings.handle_event`` with
Player/play. These adapters return True only to quit. For custom routing,
``dispatch(event)`` returns ``EventResult.UNHANDLED``, ``HANDLED``, or ``QUIT``;
compare explicitly. Its Boolean conversion raises to prevent a handled key
from accidentally requesting exit. Do not pass ``dispatch`` directly to Player.
Existing Boolean handlers, including Playback.handle_event, retain their contract.

Standalone bindings work without focus:

.. code-block:: python

   from bruhanimate import KeyBinding, KeyBindings, Label, play

   state = {"count": 0}

   def increment() -> None:
       state["count"] += 1

   bindings = KeyBindings(
       KeyBinding("space", increment, description="increment"),
       KeyBinding.character("q", quit=True, description="quit"),
   )
   play(Label(lambda: f"Count: {state['count']}"),
        event_handler=bindings.handle_event, frames=180)

KeyBindings alone installs no default quit keys. Exceptions from actions
propagate through Player's normal cleanup. Handlers run synchronously: keep
actions short, and queue solver work for update (as Playback.step does).

Visibility, resize, and ownership
---------------------------------

A target belongs to one group and attaches to one panel. The group borrows its
targets; Panel/Scene/layout continue to own and close content. A target becomes
available after successful Panel startup. ``target.enabled=False`` removes it
from navigation without hiding or pausing content. ``panel.set_visible(False)``
hides the panel and its nested focus targets while updates continue.

Layouts automatically mark zero-area slots unavailable, including nested panels.
Initially hidden factories remain uncalled. Already started content retains its
state and continues updating while hidden. When selection becomes unavailable,
focus moves to the next available target in declaration order, wrapping if
needed even with ``wrap=False``; this fallback is separate from manual navigation.
If none remain, ``focus.focused`` is None. Showing or enabling another target
does not steal focus from an available selection.

Closing a panel, failing its startup, or expiring its enclosing TimedOverlay
removes its target from focus. After close, the target may attach to a replacement
panel in the same group. Never attach it to two live panels. Focus availability
does not detect arbitrary Layer clipping, offscreen motion, or overlap by another
window; use ``enabled`` or ``set_visible`` for those application decisions.
Layouts control their children's visibility during reflow; use ``enabled`` for
a persistent exclusion from keyboard navigation.

ScrollView and LogView expose reusable ``bindings`` for arrows, Page Up/Down,
Home/End; attach them with ``FocusTarget("log", log.bindings)``. See :doc:`views`.

For a complete three-panel example, run ``python -m bruhanimate.demos.dashboard_demo``.
See :doc:`demos/dashboard_demo` for solver/signal/log controls. This API provides
keyboard routing and focus; mouse input, editable fields, and nested focus scopes
remain outside its scope.

API
---

.. automodule:: bruhanimate.keyboard
   :members:
