"""Ship occlusion, resize continuity and immutable presentation in the demo."""

from copy import deepcopy

import numpy as np

from bruhanimate import Buffer
from bruhanimate.demos.warp_demo import build_scene


def test_hull_occludes_stars_but_surrounding_cells_remain_transparent():
    scene = build_scene(Buffer(24, 80))
    stars, ship = (layer.animation for layer in scene.layers)
    scene.start()
    try:
        stars.buffer.buffer = [["*"] * 80 for _ in range(24)]
        frame = Buffer(24, 80)
        scene.draw(frame)
        sprite = ship.ships[ship.active]
        x, y = map(int, sprite.position)
        art = ship.clips[ship.active].frames[sprite.frame_index]
        for row, cells in enumerate(art.cells):
            for column, cell in enumerate(cells):
                assert frame.get_char(x + column, y + row) == (cell or "*")
        original = deepcopy(frame.buffer)
        phase = ship.phase
        scene.draw(Buffer(24, 80))
        assert ship.phase == phase
        scene.update(1 / 30)
        assert frame.buffer == original
    finally:
        scene.close()


def test_resize_preserves_flight_star_positions_and_engine_phase():
    scene = build_scene(Buffer(24, 80))
    stars, ship = (layer.animation for layer in scene.layers)
    scene.start()
    try:
        for _ in range(13):
            scene.update(1 / 60)
        phase = ship.phase
        frame_indices = [sprite.frame_index for sprite in ship.ships]
        points = stars._stars.copy()
        random_state = deepcopy(stars.np_rng.bit_generator.state)
        for size, expected in [((5, 3), 1), ((1, 1), 2), ((80, 24), 0)]:
            scene.resize(size)
            assert ship.active == expected
            assert ship.phase == phase
            assert [sprite.frame_index for sprite in ship.ships] == frame_indices
            np.testing.assert_array_equal(stars._stars, points)
            assert stars.np_rng.bit_generator.state == random_state
            scene.draw(Buffer(size[1], size[0]))
        scene.update(1 / 60)
        assert ship.phase > phase
    finally:
        scene.close()
        scene.close()
    assert not stars._started
    assert all(sprite._closed for sprite in ship.ships)
