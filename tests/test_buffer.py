import pytest

from bruhanimate.bruhutil.bruhffer import Buffer


def test_buffer_init():
    """Verify buffer initialization."""
    b = Buffer(10, 20)
    assert b.height() == 10
    assert b.width() == 20
    assert len(b.buffer) == 10
    assert len(b.buffer[0]) == 20


def test_buffer_put_char():
    """Test placing a character in the buffer."""
    b = Buffer(5, 5)
    b.put_char(2, 2, "X")
    assert b.get_char(2, 2) == "X"
    assert b.get_char(0, 0) == " "


def test_buffer_put_at():
    """Test placing a string in the buffer."""
    b = Buffer(5, 10)
    b.put_at(2, 1, "HELLO")
    # Buffer is a list of lists of characters
    assert "".join(b.buffer[1][2:7]) == "HELLO"


def test_buffer_clear():
    """Test clearing the buffer."""
    b = Buffer(5, 5)
    b.put_char(0, 0, "X")
    b.clear_buffer(val=".")
    for row in b.buffer:
        for char in row:
            assert char == "."


def test_buffer_get_char_out_of_bounds():
    """Ensure get_char returns None for out-of-bounds coordinates."""
    b = Buffer(5, 5)
    assert b.get_char(10, 10) is None
    assert b.get_char(-1, -1) is None


@pytest.mark.parametrize(
    "region, expected",
    [
        ({"x": 2, "w": 3, "h": 1}, ["abX", "def"]),
        ({"y": 1}, ["abc", "XXX"]),
        ({"x": 1, "y": 1}, ["abc", "dXX"]),
        ({"x": -1, "y": -1, "w": 3, "h": 2}, ["XXc", "def"]),
        ({"x": -1, "y": -1}, ["XXX", "XXX"]),
        ({"x": 1, "y": 1, "w": 99, "h": 99}, ["abc", "dXX"]),
        ({"w": 0}, ["abc", "def"]),
        ({"h": 0}, ["abc", "def"]),
        ({"w": -1}, ["abc", "def"]),
        ({"h": -1}, ["abc", "def"]),
        ({"x": 3}, ["abc", "def"]),
        ({"y": 2}, ["abc", "def"]),
        ({"x": -3, "w": 2}, ["abc", "def"]),
        ({"y": -3, "h": 2}, ["abc", "def"]),
    ],
)
def test_partial_clear_clips_without_changing_dimensions(region, expected):
    buffer = Buffer(2, 3)
    buffer.put_at(0, 0, "abc")
    buffer.put_at(0, 1, "def")

    assert buffer.clear_buffer(**region, val="X") is buffer

    assert ["".join(row) for row in buffer.buffer] == expected
    assert len(buffer.buffer) == buffer.height() == 2
    assert all(len(row) == buffer.width() == 3 for row in buffer.buffer)


def test_cleared_rows_are_independent_and_support_transparency():
    buffer = Buffer(2, 3).clear_buffer(val=None)
    buffer.put_char(1, 0, "X")

    assert buffer.buffer == [[None, "X", None], [None, None, None]]


@pytest.mark.parametrize("height, width", [(-1, 3), (2, -1)])
def test_negative_buffer_dimensions_are_rejected(height, width):
    with pytest.raises(ValueError, match="dimensions"):
        Buffer(height, width)


@pytest.mark.parametrize("method", ["sync_with", "sync_over_top", "get_buffer_changes"])
@pytest.mark.parametrize("size", [(1, 3), (3, 3), (2, 2), (2, 4)])
def test_incompatible_buffers_are_rejected_before_mutation(method, size):
    buffer = Buffer(2, 3).clear_buffer(val=".")
    other = Buffer(*size).clear_buffer(val="X")

    with pytest.raises(ValueError, match="dimensions must match"):
        result = getattr(buffer, method)(other)
        if method == "get_buffer_changes":
            list(result)

    assert buffer.buffer == [["."] * 3, ["."] * 3]


def test_buffer_copy_does_not_alias_source_rows():
    source = Buffer(2, 3).clear_buffer(val="X")
    target = Buffer(2, 3)
    target.sync_with(source)
    source.put_char(0, 0, "Y")
    target.put_char(1, 1, "Z")

    assert target.buffer == [["X", "X", "X"], ["X", "Z", "X"]]
    assert source.buffer == [["Y", "X", "X"], ["X", "X", "X"]]


def test_overlay_distinguishes_transparent_cells_from_spaces():
    target = Buffer(2, 3).clear_buffer(val="X")
    overlay = Buffer(2, 3).clear_buffer(val=None)
    overlay.put_char(1, 0, " ")
    overlay.put_char(2, 1, "Y")

    target.sync_over_top(overlay)

    assert target.buffer == [["X", " ", "X"], ["X", "X", "Y"]]


@pytest.mark.parametrize("shift", [-10, -1, 0, 1, 10])
def test_scrolling_preserves_dimensions_and_independent_rows(shift):
    buffer = Buffer(3, 3)
    for y, text in enumerate(["abc", "def", "ghi"]):
        buffer.put_at(0, y, text)

    buffer.scroll(shift)

    original = ["abc", "def", "ghi"]
    expected = [original[y + shift] if 0 <= y + shift < 3 else "   " for y in range(3)]
    assert ["".join(row) for row in buffer.buffer] == expected
    assert len({id(row) for row in buffer.buffer}) == 3
    assert all(len(row) == 3 for row in buffer.buffer)


@pytest.mark.parametrize("size", [(0, 3), (2, 0), (0, 0)])
def test_empty_buffers_preserve_dimensions(size):
    buffer = Buffer(*size)
    buffer.clear_buffer(val=None)
    buffer.scroll(1)
    buffer.scroll(-1)
    buffer.sync_with(Buffer(*size))
    buffer.sync_over_top(Buffer(*size))

    assert len(buffer.buffer) == size[0]
    assert all(len(row) == size[1] for row in buffer.buffer)
    assert list(buffer.get_buffer_changes(Buffer(*size))) == []


@pytest.mark.parametrize(
    "shift,expected",
    [
        (0, "ABCD"),
        (1, "DABC"),
        (-1, "BCDA"),
        (4, "ABCD"),
        (5, "DABC"),
        (-5, "BCDA"),
        (1001, "DABC"),
    ],
)
def test_horizontal_rotation_has_consistent_direction_and_wrap(shift, expected):
    whole, single = Buffer(2, 4), Buffer(2, 4)
    for buffer in (whole, single):
        buffer.put_at(0, 0, "ABCD")
        buffer.put_at(0, 1, "ABCD")
    whole.shift(shift)
    single.shift_line(1, shift)
    assert whole.buffer == [list(expected), list(expected)]
    assert single.buffer == [list("ABCD"), list(expected)]
    whole.put_char(0, 0, "!")
    assert whole.buffer[1] == list(expected)


def test_rotating_empty_rows_is_inert():
    buffer = Buffer(2, 0)
    buffer.shift(5)
    buffer.shift_line(1, -5)
    assert buffer.buffer == [[], []]
