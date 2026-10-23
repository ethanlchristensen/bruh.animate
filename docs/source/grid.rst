Grid viewport
=============

draw_grid infers rectangular board dimensions, draws visible cells, and returns
a GridViewport for paths, text, and markers. It supports spacing, centering,
absolute x/y origins, board-space camera offsets, and clipped screen regions.
Oversized boards anchor at the region's top left. Empty boards draw nothing;
ragged rows are rejected. Offscreen cells do not invoke glyph callbacks.

.. code-block:: python

   from bruhanimate import Buffer, draw_grid

   buffer = Buffer(10, 30)
   grid = draw_grid(buffer, ("S...", ".##.", "...E"), spacing=(2, 1),
                    region=(0, 1, 30, 8))
   grid.path(((0, 0), (1, 0), (2, 0)), "*")
   grid.put(3, 2, "@")

Glyph styling accepts a mapping or glyph(value, column, row) callback. None is
transparent; spaces paint. Use one printable character, optionally ANSI SGR
styled. Wide/combining glyphs and cursor controls are rejected. Ambiguous-width
glyphs assume one terminal cell. Grid drawing leaves gaps and outside cells alone.

.. automodule:: bruhanimate.grid
   :members:
