Tile maps and top-down games
============================================

``Tile`` and ``TileMap`` are immutable, shareable data. ``Camera2D`` holds an
independent viewport position. Use them with the ordinary Player, sprites and
callbacks; they do not introduce another playback loop or resource owner.

Building and drawing a map
--------------------------------------------

.. code-block:: python

   from bruhanimate import Buffer, Camera2D, Tile, TileMap

   world = TileMap(
       ["########", "#......#", "#..#...#", "########"],
       {"#": Tile("#", solid=True), ".": Tile(".")},
   )
   camera = Camera2D((5, 3), world_size=(world.width, world.height))
   camera.follow((4, 1))
   target = Buffer(5, 7)
   world.draw(target, camera=camera, origin=(1, 1))
   assert camera.world_to_screen((4, 1), origin=(1, 1)) == (3, 2)

Rows and the definition mapping are copied at construction; every ID must have
a Tile definition. String rows use individual characters as IDs; nested cell
sequences also support longer IDs such as ``"floor"``. Maps must be nonempty
rectangles. Tile glyphs occupy one terminal cell and may include ANSI SGR styles.
``None`` is visually transparent and spaces paint. Collision is independent of
appearance: a transparent tile can be solid, and a visible tile can be walkable.

Draw multiple maps in order to compose layers. Choose which map supplies
collision queries explicitly. Draw visits only visible cells and does not
change the map or camera. ``origin`` places the camera viewport on screen;
optional ``clip=(x, y, width, height)`` further restricts destination cells.
Without a camera, world (0, 0) is placed at origin and clipped to the Buffer.
Maps have no start/update/close methods: wrap a drawing callback when placing
one in Scene. Gameplay edits can construct a replacement map, or use separate
application state for doors and triggers; no tile-editing API is implied.

Camera coordinates and follow
--------------------------------------------

``Camera2D(viewport=(width, height))`` uses integer cell dimensions. Position is
the world cell at the top left. ``world_to_screen`` and ``screen_to_world`` are
inverse translations, including outside points, with an optional screen origin.
They do not clip. A camera has no target ownership and does not update itself.

Call ``follow(target)`` during application updates to put the target at the
center cell. Even viewport sizes use the right/bottom center. An explicit
``dead_zone=(x, y, width, height)`` keeps the camera still while the target is
inside that viewport-relative rectangle. The zone must be nonempty and fit
inside the viewport. Following moves immediately, without smoothing.

.. code-block:: python

   from bruhanimate import Camera2D

   camera = Camera2D((10, 6), world_size=(40, 20), position=(5, 5))
   camera.follow((8, 7), dead_zone=(2, 1, 5, 3))
   assert camera.position == (5, 5)
   camera.follow((13, 9), dead_zone=(2, 1, 5, 3))
   assert camera.position == (7, 6)
   camera.resize((50, 30))
   assert camera.position == (0, 0)

Optional ``world_size`` clamps position to a world starting at (0, 0), taking
precedence over follow near its edges. Small worlds stay at the top left of
larger viewports. An unbounded camera permits negative positions. Resize changes
viewport dimensions and clamps existing position; follow again explicitly if
desired. ``visible_bounds`` is the entire world-space view rectangle, including
any area beyond a small world. Neither tiles nor camera apply cell-aspect
correction, zoom or rotation.

Queries and movement
--------------------------------------------

.. code-block:: python

   from bruhanimate import Tile, TileMap

   world = TileMap(
       [".....", "..#..", "....."],
       {".": Tile("."), "#": Tile("#", solid=True)},
   )
   assert world.tile_at((2, 1)).solid
   assert world.collides((2, 1, 1, 1))
   assert world.move((0, 1, 1, 1), (1000, 1)) == (1, 2)

Rectangles are half-open ``(x, y, width, height)`` in world cells. Merely touching
an edge is not overlap. ``collides`` treats outside cells as solid by default;
``outside_solid=False`` checks only the map intersection. Zero-area queries never
collide. ``tile_at`` raises IndexError outside the map rather than wrapping
negative indices.

``move(bounds, delta)`` returns the new top-left cell without changing any state.
The starting rectangle must have positive dimensions and be entirely inside
walkable space. Movement sweeps each crossed leading edge, resolves X then Y,
and stops against solid tiles and map boundaries. Thus large integer deltas
cannot tunnel through a wall, and the second axis may slide along it. Work is
bounded by map dimensions even for huge deltas. This is axis-separated grid
movement; it does not model continuous velocity, time of impact, dynamic-body
collisions, or a straight diagonal path. Keep visual and collision bounds
explicit in application code.

Playable example and deterministic ticks
--------------------------------------------

Run ``python -m bruhanimate.demos.topdown_demo``. Explore the original map and
collect five stars using arrows or WASD. P pauses, R resets, and Q/Escape quits.
The HUD reports progress and remains active after all stars are found.

The demo converts KeyBindings into a bounded :class:`~bruhanimate.ActionQueue`. It
accepts at most 16 pending commands, dropping newly arriving commands when full,
and consumes one command per simulation update at 12 updates/second. Quit is
immediate. Movement commands received while paused are consumed without moving;
pause also stops sprite updates. Reset clears pending commands and restores the
position, collectibles and unpaused state; it preserves the decorative sprite's
clip clock. Terminal key repeats produce repeated commands. There is no held-key
or key-release detection, and movement speed depends on delivered commands.

Events are routed explicitly through Player's event_handler. Draw never polls
input or consumes commands. Resize changes only the view; world position and
collection state survive. On very small terminals, the HUD hides to leave room
for the player. Map construction, scoring, pause behavior and collectibles are
application code in the demo. Applying the same commands at the same update
indices reproduces world state independently of viewport size. This is not a
persistent recording/replay format or a general action-mapping API.

.. code-block:: python

   from bruhanimate import capture
   from bruhanimate.demos.topdown_demo import TopDownGame

   game = TopDownGame((30, 10))
   game.handle_event(ord("d"))
   frames = []
   capture(game, width=30, height=10, frames=2, on_frame=frames.append)
   assert game.position == (3, 2)

Camera and map have no lifecycle or completion state. The demo owns and closes
its Sprite, is single-use after close, and stays endless until quit or a playback
limit. Capture owns the supplied game just as Player does. For split views, share
map values and give each view its own camera and live sprite instances.

API
--------------------------------------------

.. autoclass:: bruhanimate.Camera2D
   :members:

.. automodule:: bruhanimate.tilemap
   :members:
