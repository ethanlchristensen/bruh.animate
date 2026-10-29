from dataclasses import FrozenInstanceError
from random import Random

import pytest

from bruhanimate import Buffer, Camera2D, Tile, TileMap


def world(rows):
    return TileMap(rows, {".": Tile("."), "#": Tile("#", solid=True)})


def test_maps_snapshot_input_and_separate_visual_and_collision_data():
    rows = [["floor", "wall"]]
    tiles = {"floor": Tile(" "), "wall": Tile(None, solid=True)}
    grid = TileMap(rows, tiles)
    rows[0][0] = "wall"
    tiles.clear()
    assert not grid.collides((0, 0, 1, 1))
    assert grid.collides((1, 0, 1, 1))
    buffer = Buffer(1, 2).clear_buffer(val="X")
    grid.draw(buffer)
    assert buffer.buffer == [[" ", "X"]]
    with pytest.raises(FrozenInstanceError):
        grid.rows = ()
    with pytest.raises(TypeError):
        grid.tiles["floor"] = Tile("x")


@pytest.mark.parametrize("rows", [[], [""], ["..", "."], ["?"], [[1]]])
def test_invalid_maps(rows):
    with pytest.raises(ValueError):
        world(rows)


@pytest.mark.parametrize("glyph", ["xx", "界", "\x1b[2JX", "\t"])
def test_invalid_tiles(glyph):
    with pytest.raises(ValueError):
        Tile(glyph)


@pytest.mark.parametrize("point", [(-1, 0), (2, 0), (0, -1), (0, 1)])
def test_lookup_never_wraps_negative_indexes(point):
    with pytest.raises(IndexError):
        world([".#"]).tile_at(point)


def test_collision_empty_edges_and_enormous_bounds():
    grid = world(["...", ".#.", "..."])
    assert not grid.collides((0, 0, 1, 1))
    assert grid.collides((1, 1, 1, 1))
    assert not grid.collides((-100, -100, 0, 5))
    assert grid.collides((-1, 0, 1, 1))
    assert not grid.collides((-1, 0, 1, 1), outside_solid=False)
    huge = 10**100
    assert grid.collides((-huge, -huge, huge * 2, huge * 2), outside_solid=False)
    assert not world(["..."]).collides(
        (-huge, -huge, huge * 2, huge * 2), outside_solid=False
    )


def test_movement_sweeps_large_deltas_and_slides_x_then_y():
    grid = world([".....", "..#..", ".....", "....."])
    assert grid.move((0, 1, 1, 1), (10**100, 0)) == (1, 1)
    assert grid.move((4, 1, 1, 1), (-(10**100), 0)) == (3, 1)
    assert grid.move((0, 1, 1, 1), (4, 2)) == (1, 3)
    assert grid.move((2, 3, 1, 1), (0, -(10**100))) == (2, 2)
    assert grid.move((2, 0, 1, 1), (0, 10**100)) == (2, 0)
    assert grid.move((0, 2, 2, 2), (100, 0)) == (3, 2)


@pytest.mark.parametrize(
    "bounds", [(-1, 0, 1, 1), (0, 0, 0, 1), (0, 0, 4, 1), (1, 0, 1, 1)]
)
def test_movement_rejects_invalid_start(bounds):
    with pytest.raises(ValueError):
        world([".#."]).move(bounds, (1, 0))


@pytest.mark.parametrize("seed", range(8))
def test_sweep_matches_slow_unit_step_reference(seed):
    rng = Random(seed)
    grid = world(
        [
            "".join("#" if rng.random() < 0.15 else "." for _ in range(12))
            for _ in range(9)
        ]
    )
    for _ in range(60):
        x, y, w, h = (
            rng.randrange(12),
            rng.randrange(9),
            rng.randrange(1, 4),
            rng.randrange(1, 3),
        )
        if grid.collides((x, y, w, h)):
            continue
        delta = rng.randrange(-20, 21), rng.randrange(-20, 21)
        expected = [x, y]
        for axis, distance in enumerate(delta):
            step = 1 if distance > 0 else -1
            for _ in range(abs(distance)):
                trial = expected.copy()
                trial[axis] += step
                if grid.collides((*trial, w, h)):
                    break
                expected = trial
        assert grid.move((x, y, w, h), delta) == tuple(expected)


def test_map_camera_origin_and_clip_draw_only_intersection_without_mutation():
    grid = TileMap(["ABCDE", "FGHIJ", "KLMNO"], {c: Tile(c) for c in "ABCDEFGHIJKLMNO"})
    camera = Camera2D((3, 2), position=(1, 1))
    buffer = Buffer(4, 6).clear_buffer(val=".")
    grid.draw(buffer, camera=camera, origin=(2, 1), clip=(3, 0, 3, 3))
    assert buffer.buffer == [
        list("......"),
        list("...HI."),
        list("...MN."),
        list("......"),
    ]
    assert camera.position == (1, 1)
    camera.position = (10**100, -(10**100))
    grid.draw(buffer, camera=camera)
    assert buffer.buffer[1] == list("...HI.")


def test_camera_follow_dead_zone_bounds_and_resize():
    camera = Camera2D((10, 6), world_size=(30, 20))
    camera.follow((12, 9))
    assert camera.position == (7, 6)
    camera.follow((29, 19))
    assert camera.position == (20, 14)
    camera.position = (5, 5)
    camera.follow((8, 7), dead_zone=(2, 1, 5, 3))
    assert camera.position == (5, 5)
    camera.follow((13, 9), dead_zone=(2, 1, 5, 3))
    assert camera.position == (7, 6)
    camera.follow((4, 4), dead_zone=(2, 1, 5, 3))
    assert camera.position == (2, 3)
    camera.resize((100, 100))
    assert camera.position == (0, 0) and camera.visible_bounds == (0, 0, 100, 100)


@pytest.mark.parametrize("point", [(0, 0), (-5, -7), (10**100, 15)])
def test_camera_transform_roundtrips(point):
    camera = Camera2D((5, 3), position=(-7, 8))
    screen = camera.world_to_screen(point, origin=(2, -3))
    assert camera.screen_to_world(screen, origin=(2, -3)) == point


@pytest.mark.parametrize(
    "zone", [(0, 0, 0, 1), (-1, 0, 1, 1), (0, 0, 6, 1), (0, 3, 1, 1)]
)
def test_camera_bad_follow_is_atomic(zone):
    camera = Camera2D((5, 3), position=(8, 9))
    with pytest.raises(ValueError):
        camera.follow((100, 100), dead_zone=zone)
    assert camera.position == (8, 9)


@pytest.mark.parametrize("bad", [(True, 0), (1.5, 0), [0, 0], (0,)])
def test_integer_coordinates_are_validated(bad):
    grid = world(["..."])
    camera = Camera2D((2, 1))
    with pytest.raises(TypeError):
        grid.tile_at(bad)
    with pytest.raises(TypeError):
        grid.move((0, 0, 1, 1), bad)
    with pytest.raises(TypeError):
        camera.position = bad
    assert camera.position == (0, 0)


def test_camera_invalid_resize_and_world_size_are_atomic():
    camera = Camera2D((2, 2), position=(5, 6))
    with pytest.raises(ValueError):
        camera.resize((0, 2))
    assert camera.viewport == (2, 2) and camera.position == (5, 6)
    with pytest.raises(ValueError):
        Camera2D((2, 2), world_size=(-1, 5))


def test_definition_and_flag_validation():
    with pytest.raises(TypeError):
        Tile("x", solid=1)
    with pytest.raises(ValueError):
        TileMap(["x"], {"": Tile("x")})
    with pytest.raises(TypeError):
        TileMap(["x"], {"x": "x"})
    with pytest.raises(TypeError):
        world(["."]).collides((0, 0, 1, 1), outside_solid=1)
