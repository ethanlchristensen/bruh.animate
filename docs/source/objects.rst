Sprites, shapes, and dynamic groups
============================================

``SpriteAsset`` stores immutable rectangular cell art. ``SpriteClip`` combines
equally sized assets into an immutable animation. Share these values freely;
give each owner a separate ``Sprite`` instance for its position and clock.
``ObjectGroup`` owns named animations and applies membership changes between
updates. It fits inside a :class:`~bruhanimate.Scene` like any other animation.

Sharing art, keeping independent state
--------------------------------------------

.. code-block:: python

   from bruhanimate import ObjectGroup, Sprite, SpriteAsset, SpriteClip, capture

   clip = SpriteClip(
       [SpriteAsset.from_text(text) for text in ("-o-", "/o\\", "\\o/")],
       frame_duration=0.15,
   )
   group = ObjectGroup({
       "fast": Sprite(clip, position=(1, 1), velocity=(5, 0)),
       "slow": Sprite(clip, position=(1, 3), velocity=(2, 0)),
   })
   frames = []
   capture(group, width=30, height=6, frames=12, fps=30, on_frame=frames.append)
   assert frames

Assets copy their input rows. ``SpriteAsset.from_text`` accepts plain multiline
text, pads short rows with transparent cells, and optionally maps one character
to transparency with ``transparent=" "``. For styled art, pass rows of cell
strings directly, for example ``SpriteAsset([["\x1b[31mX\x1b[0m", None]])``.
Each string must contain exactly one terminal cell plus optional ANSI SGR style.
Wide/combining characters, cursor commands and multi-character cells are rejected.
``None`` is transparent; ordinary spaces paint.

Positions use columns and rows; velocities use columns/second and rows/second.
Floating positions are floored when drawing, including negative positions.
``origin=(x, y)`` is an integer anchor subtracted from position. ``flip_x`` and
``flip_y`` reverse cell order within the frame rectangle while keeping this
anchor fixed. ``clip=(x, y, width, height)`` restricts destination cells.
Draw visits only the visible intersection, never advances time, and never
retains its destination buffer. Resize does not reset position or clip progress.

Start a sprite before updating it. Repeated start preserves state. Close is
idempotent, including before start, and a closed instance cannot restart.
Hidden sprites keep updating. Static art and repeating clips report
``finished=None``. A finite clip (``repeat=False``) becomes finished after the
last frame's full duration, holds that frame and continues moving. Put a finite
sprite directly in a Scene when its completion should participate in Scene's
completion policy. ObjectGroup intentionally remains endless.

Clipped drawing primitives
--------------------------

.. code-block:: python

   from bruhanimate import Buffer, draw_ellipse, draw_line, draw_rect

   target = Buffer(8, 24)
   draw_rect(target, (1, 1, 22, 6), ".")
   draw_ellipse(target, (8, 2, 10, 4), "~", filled=True)
   draw_line(target, (-1000000, 4), (1000000, 4), "-", clip=(2, 2, 20, 4))
   assert target.get_char(2, 4) == "-"

All coordinates are integer terminal cells. Rectangles and ellipses take
``(x, y, width, height)``; zero dimensions paint nothing. Lines include both
endpoints and produce the same raster when reversed. An ellipse tests cell
centers; its outline includes cells with a four-way neighbor outside the shape.
Clipping preserves the original outline instead of drawing a new border at the
viewport edge. Work is bounded by the viewport, even for huge offscreen shapes.
Every function accepts a single cell glyph with optional ANSI SGR styling.

These are cell-space primitives. Terminal cells are usually taller than they
are wide: use wider ellipse bounds for a visually circular shape. Physical cell
metrics, polygons, curves and depth rendering are not part of these helpers.

Queued membership and ownership
-------------------------------

.. code-block:: python

   from bruhanimate import Buffer, ObjectGroup, Sprite, SpriteAsset

   group = ObjectGroup()
   group.add("marker", Sprite(SpriteAsset.from_text("@")))
   assert group.names == ()  # accepted, but not yet applied
   group.start()
   try:
       assert group.names == ("marker",)
       group.remove("marker")
       group.add("replacement", Sprite(SpriteAsset.from_text("+")))
       group.update(0)  # close marker, start replacement, then update it
       target = Buffer(2, 5)
       group.draw(target)
       assert target.get_char(0, 0) == "+"
   finally:
       group.close()

``add``, ``remove`` and ``move_to_end`` are ordered commands. Commands already
queued apply at start or the beginning of update; commands issued by a child's
startup/update/close callbacks wait until the next update. Drawing never applies
commands. Even an add followed by a remove in the same batch starts and closes
that child in command order. ``names`` and ``get`` expose applied membership;
validation considers queued commands, preventing duplicate pending names.
After queuing removal, a name can be reused for a fresh replacement instance.
Names are nonempty strings, stable until explicitly removed.

A successful add transfers ownership immediately, including pending children.
Do not share live animations between groups or other owners. Cleanup closes
still-owned children in reverse acquisition order, including children that never
started. Reordering paint order does not change cleanup order. Removed children
close before the current update and receive no further updates or draws. New
children receive the most recent resize/visibility notifications before start,
then the current update's full dt in seconds. Child callbacks may queue future
commands; they must not recursively invoke the group's lifecycle methods.

A failed membership operation closes the group and its remaining children;
the group cannot restart. Cleanup continues if a child's close raises and does
not retry that child's close. As with Scene, an exception from ordinary update
or draw propagates to its owner (usually Player), which closes it.

Groups report ``finished=None`` even when empty or when all children finish.
Remove completed children explicitly. Visibility suppresses drawing and
propagates to descendants, while updates continue. Input has no automatic group
routing: pass your application handler or FocusGroup to Player explicitly.

Children draw on one reusable viewport-sized scratch buffer, cleared to None
between children, then compose in paint order. This isolates custom animations
and snapshots cell strings, but composition scans the viewport for each child.
It is a general scene container, not a sparse renderer or an entity/component
system. Use Scene/Layer inside a child for masks or styled composition, and Panel
for local coordinates. Physics, collision, tile maps, spatial indexing and action
bindings remain application concerns.

Demo and API
------------

Run ``python -m bruhanimate.demos.objects_demo`` for shared animated flyers,
clipped scenery, and short-lived sparks added and removed by application code.
It uses the ordinary Player and supports live resize.

.. automodule:: bruhanimate.sprites
   :members:

.. automodule:: bruhanimate.geometry
   :members: draw_line, draw_rect, draw_ellipse

.. autoclass:: bruhanimate.ObjectGroup
   :members:
