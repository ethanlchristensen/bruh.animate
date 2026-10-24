Routing demo
============

.. code-block:: shell

   python -m bruhanimate.demos.routing_demo

An original, public maze fixture is solved with breadth-first search. A repeating
AnimationSequence pulses the source, traces the route, moves a short trail along
it, and draws an arrival ripple. Snow keeps running behind the board. Resize
recenters the board and highlights without restarting their clocks; q exits.

``find_route`` is application code, not part of the library's path animation API.
``build_scene(buffer)`` can also be passed to ``capture`` or ``export_animation``
for a headless preview. See :doc:`../motion` for typed helper options and
:doc:`../exports` for saving a playable clip.

.. automodule:: bruhanimate.demos.routing_demo
   :members: run, build_scene, find_route
