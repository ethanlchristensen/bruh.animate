Fire Effect
===========

With ``on_resize="resize"``, heat fields, heat spots and the last visible flame
raster follow the bottom edge. Existing columns retain their fuel variation;
new cells start cold and join normal fuel updates. Heat-spot lifetimes, wind,
swell phase and random streams are preserved. Cropped heat is discarded.
No color flicker is rerolled during resize. See :doc:`../resize`.

.. automodule:: bruhanimate.bruheffect.fire_effect
   :members:
   :undoc-members:
   :show-inheritance:
