Editable controls and modal focus
============================================

``TextInput``, ``Checkbox`` and ``Button`` are ordinary animations with their own
FocusTarget. Put them in layouts or Panels for drawing and list their ``.focus``
targets in a FocusGroup for keyboard routing. ``FocusStack`` borrows groups to
isolate nested modal scopes. Player remains the only input poller.

A small form
--------------------------------------------

.. code-block:: python

   from bruhanimate import (
       Button, Checkbox, Column, Fixed, FocusGroup, KeyBinding, KeyBindings,
       Slot, TextInput, play,
   )

   name = TextInput("name", "Explorer", max_length=32)
   enabled = Checkbox("effects", "Enable effects", checked=True)
   submitted = []

   def apply() -> None:
       submitted.append((name.value, enabled.checked))

   button = Button("apply", "Apply", apply)
   focus = FocusGroup(
       name.focus, enabled.focus, button.focus,
       global_bindings=KeyBindings(KeyBinding("ctrl+c", quit=True)),
   )
   layout = Column(
       Slot(name, size=Fixed(1)), Slot(enabled, size=Fixed(1)),
       Slot(button, size=Fixed(1)), padding=1, gap=1,
   )
   play(effect_factory=layout.build, event_handler=focus.handle_event,
        frames=120, on_resize="resize")

Controls own their targets and become eligible when started, visible and enabled.
They need no extra focusable Panel. You can wrap a control in a Panel for framing,
but do not pass its target to ``Panel(focus=...)``: that would give one target two
lifecycle owners and is rejected. Each control belongs to one animation owner,
and each target to one FocusGroup. FocusGroup and FocusStack borrow targets and
groups; they never close controls. Control close is idempotent, including before
start, and closed controls cannot restart. Resize retains their values and cursor.

Tab/Shift+Tab navigate eligible targets. Disabling a control through ``enabled``
or hiding its parent reconciles focus immediately. Showing it again does not steal
focus from an eligible sibling. Parent layout visibility, including empty slots,
propagates to controls. Clipping and arbitrary visual overlap do not infer input
eligibility: use explicit modal routing for overlays.

Editing behavior
--------------------------------------------

TextInput uses insert mode on one line. Left/right/home/end move the cursor;
backspace/delete remove characters. Enter invokes optional ``on_submit(value)``.
Printable single-cell characters insert at the cursor, including spaces and
``q``. At ``max_length`` (default 256), extra printable keys are consumed without
changing text; they cannot accidentally fall through to a global quit binding.
Unsupported events fall through to the scope. Tab is reserved by FocusGroup.

.. code-block:: python

   from bruhanimate import FocusGroup, TextInput

   field = TextInput("name", "ac")
   focus = FocusGroup(field.focus)
   field.start()
   try:
       focus.handle_event(-203)  # left
       focus.handle_event(ord("b"))
       assert field.value == "abc" and field.cursor == 2
       assert not focus.handle_event(ord("q"))
       assert field.value == "abqc"
   finally:
       field.close()

``value`` assignment validates plain single-cell text and length before mutation,
moves the cursor to the end, and invokes ``on_change(value)`` only when the value
changes. Construction does not invoke callbacks. Events edit immediately during
input routing on the playback thread; callbacks run after the value changes.
Use ActionQueue from :doc:`controls` if application work must wait for update.
Callback errors propagate to the owning Player for cleanup; committed edits are
not rolled back automatically.

Draw paints only the first local row, filling it with styled spaces as needed.
While focused, TextInput inserts a display-only ``|`` caret and horizontally
scrolls enough to keep it visible. Drawing never moves the cursor, changes text,
or calls callbacks. The caret is visible without terminal cursor manipulation or
ANSI color. Button and Checkbox use a leading ``>`` focus marker. Optional
``style=TextStyle(...)`` follows the existing color policy.

Checkbox toggles on Space/Enter and calls ``on_change(checked)`` after a change.
Its ``checked`` setter accepts only bool and also notifies only on change. Button
invokes its zero-argument action on Space/Enter; the action must return None.
Use a scope binding with ``quit=True`` to request Player exit.

These controls do not add a text/paste protocol, selection, undo, multiline
editing, pointer events or IME support. Wide/combining glyphs, inline ANSI and
control characters are rejected in values. Unicode input is limited by the
Screen backend's delivered integer events; ASCII is the portable choice.

Modal routing and restoration
--------------------------------------------

.. code-block:: python

   from bruhanimate import (
       Button, EventResult, FocusGroup, FocusStack, KeyBindings, TextInput,
   )

   background = Button("background", "Run", lambda: None)
   field = TextInput("modal-name", "Draft")
   root = FocusGroup(background.focus)
   modal = FocusGroup(field.focus, global_bindings=KeyBindings())
   router = FocusStack(root)
   background.start()
   field.set_visible(False)
   field.start()
   try:
       field.set_visible(True)
       router.push(modal)
       assert root.focused is None
       assert router.dispatch(ord("q")) is EventResult.HANDLED
       assert field.value == "Draftq"
       field.set_visible(False)  # visual/lifecycle changes belong to the app
       router.pop()
       assert root.focused is background.focus
   finally:
       router.close()
       field.close()
       background.close()

Pass ``router.handle_event`` to Player. Push suspends every lower group's input,
global shortcuts and focus highlight, while their animations can keep updating
and drawing. Only the top group receives keys. Unhandled modal events return
HANDLED so an external fallback cannot accidentally activate the background.
Even a modal with no eligible targets captures input; its global bindings still
work. Lower groups also reject direct dispatch while suspended.

Configure Escape/cancel/quit bindings on each scope explicitly. FocusStack does
not install an Escape policy or inherit root global bindings. An ordinary
FocusGroup still has its existing default quit keys unless supplied explicit
``global_bindings``. In particular, TextInput consumes printable q/Q; use an
explicit Ctrl+C/Escape binding or a button/navigation path to leave the form.

Pop removes one modal group and restores the prior target in the uncovered group
if it remains eligible; otherwise it chooses the first eligible target. Hidden,
disabled and closed controls cannot regain focus. Nested modals restore each
level independently. The root cannot be popped. A group cannot be pushed twice
or belong to two stacks.

The router does not create, hide or close animations. Hide/close modal content
before popping it. A popped group is released to standalone operation, so any
still-visible eligible controls in it may retain their own focus; they are no
longer routed by this stack. ``close`` releases all borrowed groups, restoring
standalone operation without closing their animations. It is idempotent and
disables further input through the stack. FocusStack is a router, not an
animation or a scene push/pop controller.

Custom input handlers
--------------------------------------------

FocusTarget accepts an optional ``handler(event) -> EventResult``. FocusGroup
first handles its navigation keys, then target KeyBindings, then the handler for
unmatched events, and finally that group's global bindings. The handler must
return EventResult explicitly; returning bool/None is an error. Existing
KeyBindings-only targets retain their behavior. This is the extension used by
the editors for printable characters, without enumerating every possible key.

Settings demo
--------------------------------------------

Run ``python -m bruhanimate.demos.settings_demo``. E opens the modal editor; Tab
and Shift+Tab navigate; Enter submits from the name field or activates a button;
Space toggles the checkbox. Escape cancels, and Ctrl+C quits. Apply requires a
nonblank name and updates in-memory settings; Cancel discards draft changes.
The background B shortcut is blocked while the modal is open. Resizing preserves
drafts, and a tiny viewport can hide controls without exposing background input.
No files are written and no settings are sent externally.

API
--------------------------------------------

.. autoclass:: bruhanimate.TextInput
   :members:
   :inherited-members:

.. autoclass:: bruhanimate.Checkbox
   :members:
   :inherited-members:

.. autoclass:: bruhanimate.Button
   :members:
   :inherited-members:

.. autoclass:: bruhanimate.FocusStack
   :members:
