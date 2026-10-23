Matrix Effect
=============

With ``on_resize="resize"``, existing characters, colored pixels and row timing
stay in place. Cropped rows/columns are discarded. Newly exposed cells are blank
until the next update initializes their characters and new rows' update intervals.
The notification preserves the gradient and consumes no randomness. See
:doc:`../resize`.

.. automodule:: bruhanimate.bruheffect.matrix_effect
   :members:
   :undoc-members:
   :show-inheritance:
