Terminal resize
===============

Enable live reflow with ``on_resize="resize"`` on ``play``, ``Player``, or a
typed effect's ``.play()`` method. ``ResizePolicy`` is a Literal alias containing
``"raise"`` and ``"resize"`` for editor completion. The default ``"raise"``
retains the existing ScreenResizedError and cleanup behavior.

.. code-block:: python

   from bruhanimate import Column, Fixed, Label, Slot, StatusBar, play

   layout = Column(
       Slot(Label("Resize this terminal", align="center"), size=Fixed(1)),
       Slot(Label("The same content stays alive", align="center", vertical_align="middle")),
       Slot(StatusBar("Ready", right="q quit"), size=Fixed(1)),
   )
   play(effect_factory=layout.build, on_resize="resize", fps=60, frames=180)

CLI playback accepts the same choices:

.. code-block:: shell

   bruhanimate play snow --preset light --on-resize resize
   python -m bruhanimate.demos.dashboard_demo

What survives
-------------

Player keeps the live animation and factory result, refreshes the Screen size,
notifies content, and invalidates the previous frame so every cell is repainted.
Frames and duration limits span the whole run; resizing does not restart them.
Scene retains layer clocks, and TimedOverlay retains its visibility window.
Input continues through the existing event handler. Resize errors propagate
after normal ownership cleanup; borrowed content is never closed by Player.

Row and Column recalculate their existing Fixed/Flex allocations. Previously
started children keep updating even if hidden, and still count toward finite
completion. Initially zero-area slots defer startup until visible. Each factory
runs at most once. Layout trees remain single-use after close.

Playback keeps the acquired iterator, current snapshot, pause flag, speed,
accumulated solver time and queued manual steps. Reflow itself neither consumes
a snapshot nor advances time. Normal updates still run at the configured rate.
In the :doc:`demos/dashboard_demo`, pause, resize smaller and larger, and press n
to confirm that the same solver continues one step at a time.

Panels and simulations
----------------------

``Panel(..., fit=True)`` follows the parent viewport, subtracting its border from
the content size. Use it inside layout slot factories. Content retains at least
one cell per axis; allocations too small for the border clip its footprint.
The default ``fit=False`` keeps fixed dimensions. Explicit bounds are unchanged;
``move_to((x, y))`` moves a panel without advancing its simulation.

Effect-specific adapters use the same typed ``resize((width, height))`` hook;
there is no extra flag to enable them. ``on_resize="resize"`` automatically uses
the implementation provided by the effect:

* **Snow:** the simulation fills the new width and height. Each contiguous pile
  connected to the old floor moves by the height difference, keeping its column
  and depth relative to the bottom. Other settled snow keeps absolute coordinates,
  including snow perched on configured collision surfaces. Falling flakes retain
  their coordinates, fall delay and drift when still visible and uncovered.
  Cropped pile cells/columns, cropped falling flakes and flakes covered by a
  relocated pile are discarded; later growth does not restore them. New columns
  start empty and immediately participate in spawning on the next update.
* **Plasma:** wave anchors follow the new dimensions and the whole raster is
  repainted at its existing phase. Frequencies, palette and random streams stay
  unchanged, so resize does not produce a simulation step or a random reset.
* **Fire:** both heat fields, heat spots and the last visible flame raster follow
  the bottom edge, retaining left-hand columns. Heat-spot lifetimes, wind, swell
  phase and random streams are preserved. Cropped heat/spots are discarded. New
  cells start cold; new columns use neutral fuel variation until the next normal
  random refresh. The last colored pixels are copied instead of rerolling flicker.
* **Rain:** existing drops, image splashes and lightning cells keep their absolute
  positions. Visible bottom-row splashes move to the new floor. Bolt lifetimes,
  intensity, swell direction and wind are preserved. Cropped cells are discarded;
  new space starts empty and receives rain during normal updates. Explicit collision
  masks keep their dimensions and coordinates; cells outside a mask do not collide.
* **Matrix:** existing characters, colored pixels, per-row update intervals and
  character/color ticks keep their coordinates. Cropped rows and columns are
  discarded. New cells start blank; the next simulation update chooses characters
  for them and update intervals for new rows. Repeated resizes before that tick
  retain only the pending cells still visible. Resize itself consumes no randomness.
* **Other BaseEffect simulations:** the default keeps the original private raster
  and clips its bottom/right edges. Growth reveals that raster again; cells beyond
  it reveal the player's or panel's background. These effects need individual
  adaptation rules before their simulation dimensions can change.

The adapters prepare their private buffers during the resize notification, so
preserved or relocated pixels appear before the next scheduled layer update.
New fire/rain/Matrix activity begins during normal simulation updates. Previously presented
frames remain unchanged. Explicit collision geometry is never automatically
moved or inferred from layout. An embedded terminal subprocess is not resized.
The :doc:`demos/dashboard_demo` exercises snow and plasma with the existing solver.
Try the other adapters directly:

.. code-block:: shell

   bruhanimate play fire --on-resize resize
   bruhanimate play rain --preset thunderstorm --on-resize resize
   bruhanimate play matrix --on-resize resize

Custom animations
-----------------

``ScrollView.resize`` changes only its viewport and clamps the scroll offset;
its child continues drawing on the same full canvas. ``set_content_size`` is the
explicit canvas resize operation. ``LogView.resize`` rewraps retained history,
preserving the top logical line/character while browsing or staying at the bottom
while following new messages. Neither operation consumes solver snapshots or
appends log messages. See :doc:`views` for typed options and navigation bindings.

``Resizable`` is an optional structural protocol with
``resize(size: tuple[int, int]) -> None``; size is positive (width, height) in
terminal cells. ``ResizableAnimation`` combines it with Animation, and is the
return type of ``layout.build``. Inheritance is optional. Implement the hook to
recalculate cached geometry; do not advance simulation, consume input, or restart
existing children. It may run before startup for a delayed overlay's content.
For a BaseEffect adapter, override the typed ``resize`` method, validate dimensions
before changing state, resize every dependent simulation array, and rebuild the
private raster without calling ``update`` or consuming randomness. Finish with
``super().resize(size)`` to update its drawing viewport. Replacing only ``buffer``
is unsafe for simulations with size-dependent particle arrays or collision maps.
Drawing must stay read-only and must not retain a previously presented buffer.

Animations without the hook receive the newly sized drawing buffer directly;
their draw implementation must handle arbitrary dimensions. Playback, Label,
StatusBar, ImageEffect and buffer-aware drawing callbacks already do so.
Manual users of a built layout call ``animation.resize((width, height))`` before
drawing into a differently sized buffer.

Backend behavior and limits
---------------------------

Windows refreshes console dimensions and resets cursor tracking. Unix marks a
pending signal and refreshes curses from Player's loop, outside the signal
handler. Both acknowledge the resize without reopening the terminal. Player
repaints the whole viewport even if a resize notification reports the same size.

For a temporarily empty/minimized viewport, Player waits in short intervals,
polls quit input, and checks the original duration deadline. It does not draw or
accumulate simulation catch-up while waiting. Custom Screen implementations
supporting live resize must provide ``refresh_size() -> bool``: update width and
height, reset cursor state, acknowledge the event, and return True for a positive
size; return False and leave the event pending for an empty size. Custom
presenters can override ``FramePresenter.resize()`` to invalidate their own state.
Headless capture/recording retain their configured dimensions and produce no
terminal resize events.

API
---

.. automodule:: bruhanimate.resize
   :members:
