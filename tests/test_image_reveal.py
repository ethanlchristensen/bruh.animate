import pytest

from bruhanimate import Buffer, ImageEffect, Scene


def render(image, width=5, height=2):
    frame = Buffer(height, width)
    frame.clear_buffer(val=".")
    image.draw(frame)
    return frame.buffer


def test_reveal_skips_spaces_and_holds_final_image_without_advancing_on_draw():
    image = ImageEffect([" A B", "C"], x=0, y=0, characters_per_second=2)
    image.start()
    assert render(image) == [list("....."), list(".....")]
    image.update(0.25)
    assert render(image) == [list("....."), list(".....")]
    image.update(0.25)
    first = render(image)
    assert first == render(image) == [list(".A..."), list(".....")]
    image.update(1)
    assert image.finished is True
    assert render(image) == [list(".A.B."), list("C....")]
    image.update(10)
    image.start()
    assert render(image) == [list(".A.B."), list("C....")]
    assert first == [list(".A..."), list(".....")]
    image.close()
    image.close()


def test_resize_clipping_and_movement_preserve_reveal_progress():
    image = ImageEffect("ABCD", velocity=(1, 0), characters_per_second=2)
    scene = Scene(image)
    scene.start()
    try:
        scene.update(1)
        assert render(scene, 6, 1) == [list("..AB..")]
        scene.resize((2, 1))
        assert render(scene, 2, 1) == [list("AB")]
        scene.resize((6, 1))
        assert render(scene, 6, 1) == [list("..AB..")]
        assert not scene.finished
        scene.update(1)
        assert scene.finished
        assert render(scene, 6, 1) == [list("...ABC")]
    finally:
        scene.close()


def test_default_is_immediate_and_empty_reveal_is_finished():
    image = ImageEffect("A B", x=0, y=0)
    assert image.finished is None
    assert render(image, 3, 1) == [list("A B")]
    assert ImageEffect(" \n ", characters_per_second=1).finished


def test_fractional_ticks_reach_exact_completion():
    image = ImageEffect("abc", characters_per_second=3)
    for _ in range(60):
        image.update(1 / 60)
    assert image.finished


@pytest.mark.parametrize("rate", [0, -1, float("inf"), float("nan")])
def test_invalid_reveal_rate(rate):
    with pytest.raises(ValueError, match="characters_per_second"):
        ImageEffect("x", characters_per_second=rate)


@pytest.mark.parametrize("rate", [True, "fast"])
def test_non_numeric_reveal_rate(rate):
    with pytest.raises(TypeError, match="characters_per_second"):
        ImageEffect("x", characters_per_second=rate)


@pytest.mark.parametrize("text", ["\x1b[31mx", "\t", "界", "e\u0301"])
def test_reveal_rejects_non_cell_text(text):
    with pytest.raises(ValueError, match="single-cell"):
        ImageEffect([text], characters_per_second=1)


@pytest.mark.parametrize("dt", [-1, float("nan"), float("inf")])
def test_invalid_dt_does_not_advance_reveal(dt):
    image = ImageEffect("x", characters_per_second=1)
    with pytest.raises(ValueError, match="dt"):
        image.update(dt)
    assert not image.finished
