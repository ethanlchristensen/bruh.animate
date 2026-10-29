Draw Lines Effect
=================

``Line`` construction, ``update_points``, and ``DrawLinesEffect.add_line`` accept
terminal-cell coordinates. ``get_points`` exposes the stored doubled subcell
coordinates. Updating with the same cell endpoints preserves the geometry.
Segments wholly outside an edge are skipped independently; other lines still draw.

.. automodule:: bruhanimate.bruheffect.draw_lines_effect
   :members:
   :undoc-members:
   :show-inheritance:
