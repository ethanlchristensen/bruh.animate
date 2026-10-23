Movable panels
==============

``Panel`` owns an animation drawn in local coordinates, then places it in a
parent buffer. It can frame the content, translate it, and bounce at explicit
bounds. Use ``Scene`` to stack panels back to front. ``Layer.region`` remains
a destination clip; Panel adds a separate local surface and translation.

Create a moving effect
----------------------

Use :doc:`layouts` to arrange panels automatically in rows and columns, with
typed Fixed/Flex sizing, labels, and status bars.

.. code-block:: python

   from bruhanimate import Panel, SnowEffect, effects, play

   def build(buffer):
       return Panel(
           effect_factory=lambda local: SnowEffect(local, " ", effects.snow.preset("light")),
           size=(28, 8),
           position=(2, 2),
           velocity=(18, 3),
           bounds=(0, 0, buffer.width(), buffer.height()),
           bounce=True,
           border=True,
           title="Snow",
           border_color=117,
           updates_per_second=15,
       )

   play(effect_factory=build, fps=60, updates_per_second=60, frames=180)

``size=(28, 8)`` means 28 columns by 8 rows of **content**. With a border, the
outer footprint is 30 columns by 10 rows. A child draws from local ``(0, 0)``;
with a border, that cell appears one column and row inside the outer position.
The child's simulation is never resized or cropped internally when the panel
moves. For example, fire starts at the bottom of its own local buffer.

Pass an existing animation for callbacks, images, solver playback, or a nested
Scene/Panel. Its built-in effect buffer must already match the content size:

.. code-block:: python

   from bruhanimate import ImageEffect, Panel, Scene, play

   back = Panel(ImageEffect("Back panel"), size=(20, 5), position=(2, 1), title="Back")
   front = Panel(ImageEffect("Front panel"), size=(16, 4), position=(12, 3), title="Front")
   play(Scene(back, front), frames=120)

Discovery and options
---------------------

The constructor has explicit typed keyword options: type ``Panel(`` in your
editor to browse them. Factories accept ``Buffer`` and return ``Animation``;
use typed settings classes or ``effects.snow.preset(...)`` to discover effect
options and preset names. No untyped option dictionary is required.

.. list-table:: Constructor options
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Meaning
   * - ``animation`` / ``effect_factory``
     - Supply exactly one. A factory runs once at start with a fresh local buffer.
   * - ``size: tuple[int, int]``
     - Required positive content width and height; excludes the border.
   * - ``position: tuple[float, float]``
     - Outer top-left in the parent's coordinates. Defaults to (0, 0).
   * - ``velocity: tuple[float, float]``
     - Columns/second and rows/second. Defaults to stationary (0, 0).
   * - ``bounds: tuple[int, int, int, int] | None``
     - Parent-coordinate (x, y, width, height) clip. None uses only the destination buffer's edges.
   * - ``bounce: bool``
     - Defaults to False. True requires bounds and reflects motion at their edges.
   * - ``border: bool`` / ``title: str``
     - ASCII border defaults to True. Plain single-cell title text is clipped to its top edge; a nonempty title requires a border.
   * - ``border_color`` / ``border_background``
     - Optional ANSI palette indices 0..255. None leaves that color unspecified.
   * - ``background: str | None``
     - One single-cell glyph, optionally SGR styled, for unpainted content. Defaults to a space. None allows transparency.
   * - ``updates_per_second: float | None``
     - Positive finite child update rate. None forwards every parent update.
   * - ``fit: bool``
     - False keeps fixed geometry; True follows parent resize notifications, retaining the child.
   * - ``max_catch_up: int``
     - Positive maximum child ticks per parent update; defaults to 5.

``size``, ``outer_size``, ``position``, ``velocity``, ``animation``, and
``finished`` are typed read-only properties. Position reports the current
floating-point top-left; drawing places it on terminal cells. Velocity reports
the configured rate before bounce reflection. ``animation`` is None before a
factory runs. ``move_to((x, y))`` changes position without advancing simulation.
``fit=True`` opts into parent viewport notifications; content dimensions become
parent dimensions minus the border, with a minimum of one cell on each axis.
Smaller allocations clip the border. A resize keeps the child and its clock alive.
The default ``fit=False`` preserves fixed panel geometry. Bounds remain explicit
clips even for fitting panels. See :doc:`resize`.

``focus=FocusTarget(...)`` attaches typed keyboard bindings and selection state.
Use ``FocusGroup(...).handle_event`` on Player to route input. The selected
panel draws a bold border with ``focus_border_color=226`` by default; None keeps
its normal color. ``set_visible(False)`` hides painting and removes its nested
targets from focus, while simulation and completion continue. Layouts propagate
slot visibility automatically. Arbitrary clipping and overlap do not change
focus availability; see :doc:`keyboard` for routing and ownership rules.
Wrap a larger animation in ``ScrollView`` or use ``LogView`` as the child for
scrollable text history. A fitting panel resizes their viewports while preserving
content and scroll state. See :doc:`views` for typed options and bindings.

Clipping, motion, and stacking
----------------------------------------

Negative positions are allowed. Bounds clip the entire panel, including its
frame, but never resize its local buffer. Bounds have integer coordinates and
non-negative dimensions; an empty bounds rectangle hides the panel. Offscreen
and hidden panels keep updating. An outer Layer can clip the result again.

For bouncing, the initial position clamps inside bounds. The full outer footprint
stays inside the rectangle if it fits. An oversized axis anchors at the bounds
origin and clips. Large updates can reflect across several edges. Bounds are
explicit so motion does not depend on draw being called or on the last target
buffer. Nested panels use their parent's local content coordinates.

Motion advances only in ``update(dt)``, in supplied simulation seconds. The
child's fixed-rate Layer waits for a complete interval before its first tick.
Reaching ``max_catch_up`` discards leftover child time, including the fractional
remainder; panel motion still advances by the full dt. Throttling an outer Layer
also throttles delivery to Panel, so prefer Panel's own rate to keep movement
smooth while its effect updates less often. See :doc:`composition` for timing.

Later Scene children paint over earlier ones. None cells from the child reveal
the panel background; use ``background=None`` to reveal lower layers through
unpainted cells. Plain child spaces always paint unless an outer Layer opts into
space transparency. Styling stays inside individual cells. Every frame composes
the current positions, so moving windows leave no trails and do not mutate
previously presented buffers.

Ownership, completion, and input
--------------------------------

Panel owns its supplied or factory-created animation. Do not put that child in
another owner or share its mutable buffer. Construction performs validation but
does not call the factory, start content, or acquire terminal/device resources.
Use the factory form to avoid manually matching built-in effect dimensions.

Start is idempotent while open. Close is idempotent, closes acquired content on
failed startup, and also closes a supplied child even if never started. Closing
an unstarted factory-backed panel does not call the factory. After close or a
startup failure, construct a new panel; update/draw require an open, started
instance. Player provides cleanup when update/draw fails. A factory that raises
before returning a child remains responsible for its own partial acquisitions.

Completion mirrors the child: None means endless or a factory not yet called.
Scene and Player honor finite completion normally. ``on_complete="hold"`` keeps
moving and presenting a completed panel; capture defaults to exit on completion.
For a whole temporary window, wrap Panel in ``TimedOverlay``. Wrapping only its
child hides that content on expiry but leaves the panel's frame and background.

Panel does not poll keyboard events. Pass a FocusGroup's or solver's handler to
Player/play explicitly. There are no extra loops, sleeps, threads, or terminal
handles. The :doc:`demos/windows_demo` example uses four Panel instances at
independent rates and retains its faster bouncing movement.

API
---

.. automodule:: bruhanimate.panel
   :members:
