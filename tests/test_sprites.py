from dataclasses import FrozenInstanceError

import pytest

from bruhanimate import Buffer, Sprite, SpriteAsset, SpriteClip


def clip(*, repeat=True):
    return SpriteClip(
        [SpriteAsset.from_text(char) for char in "ABC"],
        frame_duration=0.1,
        repeat=repeat,
    )


def test_assets_and_clips_snapshot_mutable_inputs():
    rows = [["A", None], [" ", "B"]]
    asset = SpriteAsset(rows)
    rows[0][0] = "C"
    frames = [asset]
    animation = SpriteClip(frames)
    frames.clear()
    assert animation.frames == (asset,)
    assert asset.cells == (("A", None), (" ", "B"))
    assert (asset.width, asset.height) == (2, 2)
    with pytest.raises(FrozenInstanceError):
        asset.cells = ()
    with pytest.raises(FrozenInstanceError):
        animation.repeat = False


def test_text_padding_and_explicit_transparency():
    assert SpriteAsset.from_text(" X\nY", transparent=" ").cells == (
        (None, "X"),
        ("Y", None),
    )
    assert SpriteAsset.from_text(" X").cells == ((" ", "X"),)


@pytest.mark.parametrize(
    "rows", [[], [[]], [["X"], ["X", "Y"]], [["界"]], [["\u0301"]], [["\x1b[2JX"]]]
)
def test_asset_rejects_invalid_art(rows):
    with pytest.raises((TypeError, ValueError)):
        SpriteAsset(rows)


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), True])
def test_invalid_clip_duration(duration):
    with pytest.raises((TypeError, ValueError)):
        SpriteClip([SpriteAsset.from_text("X")], frame_duration=duration)


def test_clip_rejects_invalid_frames_and_repeat():
    with pytest.raises(ValueError):
        SpriteClip([])
    with pytest.raises(TypeError):
        SpriteClip(["X"])
    with pytest.raises(ValueError):
        SpriteClip([SpriteAsset.from_text("X"), SpriteAsset.from_text("XX")])
    with pytest.raises(TypeError):
        SpriteClip([SpriteAsset.from_text("X")], repeat=1)


def test_instances_share_art_but_keep_independent_clocks_and_positions():
    source = clip()
    first, second = Sprite(source, velocity=(2, -1)), Sprite(source)
    first.start()
    second.start()
    first.update(0.1)
    assert first.frame_index == 1 and second.frame_index == 0
    assert first.position == (0.2, -0.1) and second.position == (0, 0)
    first.start()
    first.resize((100, 30))
    assert first.frame_index == 1 and first.position == (0.2, -0.1)
    first.close()
    second.update(0.2)
    assert second.frame_index == 2


def test_repeating_clip_wraps_and_large_dt_is_bounded():
    sprite = Sprite(clip())
    sprite.start()
    for _ in range(3):
        sprite.update(0.1)
    assert sprite.frame_index == 0
    assert sprite.finished is None
    sprite.update(1e300)
    assert 0 <= sprite.frame_index < 3


def test_finite_clip_holds_final_frame_and_continues_motion():
    sprite = Sprite(clip(repeat=False), velocity=(1, 0))
    sprite.start()
    sprite.update(0.2)
    assert sprite.frame_index == 2 and not sprite.finished
    sprite.update(0.1)
    assert sprite.finished
    sprite.update(5)
    assert sprite.frame_index == 2 and sprite.position[0] == pytest.approx(5.3)


def test_drawing_clips_floors_and_keeps_previous_frame_immutable():
    sprite = Sprite(
        SpriteAsset([list("ABC"), [None, " ", "\x1b[31mX\x1b[0m"]]), position=(-0.1, 0)
    )
    sprite.start()
    first, second = Buffer(2, 3), Buffer(2, 3)
    first.clear_buffer(val=".")
    second.clear_buffer(val=".")
    sprite.draw(first)
    sprite.draw(second)
    assert first.buffer == second.buffer
    assert first.buffer == [["B", "C", "."], [" ", "\x1b[31mX\x1b[0m", "."]]
    sprite.position = (2, 1)
    sprite.draw(second)
    assert first.buffer[1][2] == "."
    assert second.buffer[1][2] == "A"


@pytest.mark.parametrize(
    "flip_x,flip_y,expected",
    [
        (False, False, ["AB", "CD"]),
        (True, False, ["BA", "DC"]),
        (False, True, ["CD", "AB"]),
        (True, True, ["DC", "BA"]),
    ],
)
def test_flips_origin_and_clip(flip_x, flip_y, expected):
    sprite = Sprite(
        SpriteAsset.from_text("AB\nCD"),
        position=(2, 2),
        origin=(1, 1),
        flip_x=flip_x,
        flip_y=flip_y,
        clip=(1, 1, 2, 2),
    )
    buffer = Buffer(4, 4)
    sprite.draw(buffer)
    assert ["".join(row[1:3]) for row in buffer.buffer[1:3]] == expected
    assert buffer.buffer[0] == [" "] * 4


def test_hidden_sprite_advances_and_close_is_single_use():
    sprite = Sprite(clip())
    sprite.start()
    sprite.set_visible(False)
    sprite.update(0.1)
    buffer = Buffer(1, 1)
    sprite.draw(buffer)
    assert buffer.get_char(0, 0) == " "
    sprite.set_visible(True)
    sprite.draw(buffer)
    assert buffer.get_char(0, 0) == "B"
    sprite.close()
    sprite.close()
    with pytest.raises(RuntimeError):
        sprite.start()
    with pytest.raises(RuntimeError):
        sprite.update(0)
    unstarted = Sprite(SpriteAsset.from_text("X"))
    unstarted.close()
    with pytest.raises(RuntimeError):
        unstarted.start()


def test_invalid_time_and_motion_are_atomic():
    sprite = Sprite(clip(), velocity=(1e308, 0))
    with pytest.raises(RuntimeError):
        sprite.update(0)
    sprite.start()
    for dt in (-1, float("nan"), float("inf"), True, 10):
        with pytest.raises((TypeError, ValueError)):
            sprite.update(dt)
        assert sprite.position == (0, 0) and sprite.frame_index == 0
    with pytest.raises(ValueError):
        sprite.position = (float("nan"), 1)
    assert sprite.position == (0, 0)
