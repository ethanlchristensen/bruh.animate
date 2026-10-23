Layouts and text widgets
========================

``Row`` and ``Column`` arrange local animation surfaces. ``Label`` and
``StatusBar`` provide text without a custom draw callback. They compose with
Panel, Scene, and Playback and use the existing Player loop. No additional
dependencies or terminal application are required.

A small dashboard
-----------------

.. code-block:: python

   from bruhanimate import Column, Fixed, Flex, Label, Row, Slot, Spacer, StatusBar, TextStyle, play

   layout = Column(
       Slot(Label("MY DASHBOARD", align="center", style=TextStyle(bold=True)), size=Fixed(1)),
       Slot(Row(
           Slot(Label("Main content", align="center", vertical_align="middle"), size=Flex(2)),
           Spacer(Fixed(1)),
           Slot(Label(lambda: "State: ready", overflow="ellipsis"), size=Fixed(16)),
       )),
       Slot(StatusBar("Ready", right="q quit", style=TextStyle(background=24)), size=Fixed(1)),
       gap=1,
       padding=1,
   )
   play(effect_factory=layout.build, fps=60, frames=180, on_resize="resize")

Containers describe layout; they are not themselves animations. Pass
``layout.build`` as a player factory, or call ``layout.build(buffer)`` to obtain
a typed ResizableAnimation for a Scene. Nest a Row/Column inside a Slot. A tree
is single-use; construct a fresh tree for another run. Within a run,
``on_resize="resize"`` reflows the same children into new allocations.

Typed layout options
--------------------

* ``Slot(content, size=Flex())`` owns one Animation or nested Row/Column.
* ``Slot(effect_factory=callable, size=...)`` creates an Animation from an allocated
  local Buffer at startup. Supply exactly one content source.
* ``Fixed(cells)`` requests a non-negative integer extent on the main axis:
  columns in Row, rows in Column.
* ``Flex(weight=1)`` shares remaining cells by positive integer weight.
* ``Spacer(size=Flex())`` reserves space without painting or acquiring content.
* ``gap=0`` and ``padding=0`` are non-negative integers. Padding is uniform on all
  four sides. Children fill the padded cross-axis extent.
* ``background=None`` leaves gaps/padding transparent. A single-cell glyph,
  optionally SGR styled, paints the entire container before its children.

All constructor options are named and typed. Use ``Row(``, ``Slot(``, ``Fixed(``,
and ``Flex(`` for editor completion. ``layout.regions((width, height))`` returns a
tuple of local ``(x, y, width, height)`` rectangles without building or acquiring
content. It includes Spacer and empty-slot rectangles.

Allocation is deterministic. Padding and gaps reserve space first, then Fixed
requests consume it in declaration order. If fixed requests exceed the available
space, later requests shrink, possibly to zero. Flex slots share the remainder
using integer largest-remainder allocation; ties go to earlier children. If
there are no Flex slots, unused space stays at the end. Oversized gaps/padding
can leave zero-area slots whose origins lie outside the buffer.

Zero-area slots do not start children, invoke factories, update, draw, or
participate in finite completion. Supplied children in those slots are still
owned and closed during cleanup. This allows tiny terminals without constructing
zero-sized built-in simulations. Factories may assume positive local dimensions.

Effects and panels in slots
---------------------------

.. code-block:: python

   from bruhanimate import Column, Fixed, Label, Panel, Slot, SnowEffect, SnowSettings, play

   def snow_panel(local):
       border = local.width() >= 3 and local.height() >= 3
       return Panel(
           effect_factory=lambda content: SnowEffect(content, " ", SnowSettings(seed=42)),
           size=(local.width() - 2 * border, local.height() - 2 * border),
           border=border,
           title="Snow" if border else "",
           updates_per_second=15,
       )

   layout = Column(
       Slot(Label("Local animation surface"), size=Fixed(1)),
       Slot(effect_factory=snow_panel),
       gap=1,
   )
   play(effect_factory=layout.build, fps=60, updates_per_second=60, frames=180)

Each slot's child draws in local coordinates. Built-in buffers must match the
allocated size, so prefer factories to preallocated effects. A Panel inside a
slot uses that slot as its parent: its outer size includes its border, while its
``size`` is content-only. The example subtracts the border from the slot size and
uses an unframed panel when the allocation is too small for a border.

Slots clip content to their rectangles. A layout adds no update clock: every
parent update is forwarded in declaration order. Use Panel or Layer to pace an
effect independently; see :doc:`panels` and :doc:`composition`.

Labels and dynamic text
-----------------------

.. code-block:: python

   from bruhanimate import Label, TextStyle, play

   label = Label(
       "Aligned text\nwith a second line",
       align="center",
       vertical_align="middle",
       overflow="ellipsis",
       style=TextStyle(foreground=117, background=235, bold=True),
   )
   play(label, frames=60)

``Label`` accepts a string or a zero-argument callback returning a string.
Callbacks are not called during construction or drawing. They are evaluated
once at start and once per update; draw uses cached text, available through the
read-only ``text`` property. Callbacks should be fast, read-only state getters.
Place state-producing content before dependent labels so the labels observe the
new state in the same update. Invalid callback results raise when refreshed.

Editor completion exposes:

* ``align="left" | "center" | "right"``
* ``vertical_align="top" | "middle" | "bottom"``
* ``overflow="clip" | "ellipsis" | "wrap"``
* ``style=TextStyle(foreground=None, background=None, bold=False)``
* ``fill=True`` (paint the entire local area with styled spaces).

Colors are ANSI palette indices 0..255. Newlines are supported; wide characters,
combining marks, tabs, other controls, and inline escape sequences are rejected.
Use TextStyle for per-cell ANSI styling. ``wrap`` breaks at cell boundaries, not
words. ``ellipsis`` shortens each long line using ASCII dots. Excess rows clip;
vertical alignment applies to the visible rows. ``fill=False`` leaves unpainted
cells untouched, but spaces in the text still paint.

``TextSource``, ``TextAlign``, ``VerticalAlign``, and ``TextOverflow`` are exported
type aliases for applications that expose these same options.

Status bars
-----------

``StatusBar(left="", center="", right="", style=None)`` paints one local row.
Each section is a single-line string or callback, refreshed only at start and on
updates. Use ``Slot(status, size=Fixed(1))`` in a Column. The right section has
first claim on space, then left, then center; sections clip from their ends and
keep a one-cell gap when space permits. They never overwrite one another. Extra
local rows remain untouched. Style applies to the full bar, including spaces.

Ownership, completion, and limitations
--------------------------------------

Building reserves the whole nested layout tree and transfers supplied children
to the returned animation. Duplicate supplied animation/container instances are
rejected across the tree. Factories must return fresh instances. Constructors
and build do not open resources or call factories; startup creates only visible
slot content. Closing before startup still closes supplied children without
calling factories. Cleanup covers partial startup failures and continues if a
child's close raises. Close is idempotent; built layouts cannot restart afterward.

Never share children with another owner or separately build an already-owned
nested layout. Factory code remains responsible for resources acquired before
it successfully returns a child. Dynamic labels own only their cached strings;
they do not own objects captured by callbacks. They refresh on a later start if
used independently again.

Started finite children (including subsequently hidden ones) participate in Scene's usual completion rules. Labels,
status bars, and spacers are endless. ``on_complete="hold"`` keeps backgrounds
and text updating after a solver finishes. Capture defaults to exit on finite
completion. Updates use the parent's simulation seconds, with no extra loops,
threads, input polling, or sleeping.

Keyboard polling stays on Player. Use :doc:`keyboard` to route bindings to
focused panels; layouts exclude zero-area slots from focus automatically.
Use :doc:`views` for scrollable animation canvases and bounded activity logs.
Mouse handling is not provided. With ``on_resize="resize"``, built layouts accept new viewport
sizes between frames. Existing children keep running when a slot becomes empty;
initially empty slots start only when they first become visible. Factories are
never recalled for existing content. Use ``Panel(fit=True, ...)`` in slot factories
to fit a bordered panel to its changing allocation. See :doc:`resize`. The :doc:`demos/dashboard_demo` example combines a public
beam fixture, an animated background, a statistics sidebar, and explicit solver
controls in your native terminal.

API
---

.. automodule:: bruhanimate.layout
   :members:
   :inherited-members:

.. automodule:: bruhanimate.widgets
   :members:
