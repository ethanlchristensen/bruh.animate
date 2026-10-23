Rain Effect
===========

With ``on_resize="resize"``, visible rain and lightning retain their coordinates,
and floor splashes follow the new bottom. Bolt lifetimes, intensity, wind and
swell direction are preserved. Cropped cells are discarded and new space starts
empty. Collision masks keep their dimensions and coordinates; cells beyond the
mask are non-colliding. See :doc:`../resize`.

.. automodule:: bruhanimate.bruheffect.rain_effect
   :members:
   :undoc-members:
   :show-inheritance:
