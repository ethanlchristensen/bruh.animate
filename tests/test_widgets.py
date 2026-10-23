import re

import pytest

from bruhanimate import Buffer, Label, StatusBar, TextStyle


def rows(widget, width, height=1):
    buffer = Buffer(height, width).clear_buffer(val=".")
    widget.draw(buffer)
    return [
        "".join(re.sub(r"\x1b\[[0-9;]*m", "", cell) for cell in row)
        for row in buffer.buffer
    ]


@pytest.mark.parametrize(
    "align, expected", [("left", "ab   "), ("center", " ab  "), ("right", "   ab")]
)
def test_horizontal_alignment(align, expected):
    assert rows(Label("ab", align=align), 5) == [expected]


@pytest.mark.parametrize(
    "align, expected",
    [
        ("top", ["x", " ", " "]),
        ("middle", [" ", "x", " "]),
        ("bottom", [" ", " ", "x"]),
    ],
)
def test_vertical_alignment(align, expected):
    assert rows(Label("x", vertical_align=align), 1, 3) == expected


def test_overflow_multiline_wrapping_and_tiny_sizes():
    assert rows(Label("abcdef", overflow="clip"), 4) == ["abcd"]
    assert rows(Label("abcdef", overflow="ellipsis"), 4) == ["a..."]
    assert rows(Label("abcdef", overflow="ellipsis"), 2) == [".."]
    assert rows(Label("abcdef\n\nz", overflow="wrap"), 3, 4) == [
        "abc",
        "def",
        "   ",
        "z  ",
    ]
    assert rows(Label("long" * 10000, overflow="wrap"), 2, 1) == ["lo"]
    assert rows(Label("x"), 0, 1) == [""]
    assert rows(Label("x"), 1, 0) == []


def test_fill_false_preserves_surroundings_but_text_spaces_paint():
    assert rows(Label("a b", align="center", fill=False), 5, 2) == [".a b.", "....."]


def test_style_is_applied_per_cell_and_only_affects_this_widget():
    label = Label("é", style=TextStyle(foreground=117, background=24, bold=True))
    buffer = Buffer(1, 2)
    label.draw(buffer)
    assert buffer.buffer[0] == [
        "\x1b[1;38;5;117;48;5;24mé\x1b[0m",
        "\x1b[1;38;5;117;48;5;24m \x1b[0m",
    ]


def test_dynamic_label_snapshots_start_and_updates_but_never_draw():
    calls = []

    def text():
        calls.append(1)
        return str(len(calls))

    label = Label(text)
    assert label.text == "" and calls == []
    label.start()
    label.start()
    assert rows(label, 2) == ["1 "]
    assert rows(label, 2) == ["1 "] and len(calls) == 1
    label.update(1 / 60)
    assert rows(label, 2) == ["2 "] and label.text == "2"
    label.close()
    label.close()
    with pytest.raises(RuntimeError):
        label.update(0)


@pytest.mark.parametrize(
    "width, expected",
    [(15, "L      C      R"), (5, "L C R"), (3, "L R"), (1, "R"), (0, "")],
)
def test_statusbar_sections_never_overlap(width, expected):
    status = StatusBar("L", center="C", right="R")
    assert rows(status, width) == [expected]
    assert rows(status, width, 2)[1] == "." * width


def test_statusbar_right_priority_and_center_gets_remaining_space():
    assert rows(StatusBar("abcdefgh", center="center", right="q quit"), 10) == [
        "abc q quit"
    ]
    assert rows(StatusBar(center="mid"), 7) == ["  mid  "]
    assert rows(StatusBar("left"), 7) == ["left   "]


def test_dynamic_statusbar_is_cached_and_rejects_multiline_callbacks():
    calls = []

    def text():
        calls.append(1)
        return str(len(calls))

    status = StatusBar(text, right="q")
    assert calls == []
    status.start()
    status.start()
    assert rows(status, 3) == ["1 q"]
    assert rows(status, 3) == ["1 q"] and len(calls) == 1
    status.update(0.1)
    assert rows(status, 3) == ["2 q"]
    status.close()
    with pytest.raises(RuntimeError):
        status.update(0)
    with pytest.raises(ValueError):
        StatusBar(lambda: "two\nlines").start()


@pytest.mark.parametrize(
    "factory, error",
    [
        (lambda: Label("x", align="start"), ValueError),
        (lambda: Label("x", vertical_align="center"), ValueError),
        (lambda: Label("x", overflow="scroll"), ValueError),
        (lambda: Label("x", fill=1), TypeError),
        (lambda: Label(42), TypeError),
        (lambda: Label("x", style="red"), TypeError),
        (lambda: StatusBar(style=42), TypeError),
        (lambda: Label("界"), ValueError),
        (lambda: Label("e\u0301"), ValueError),
        (lambda: Label("\t"), ValueError),
        (lambda: Label("\x1b[31mx"), ValueError),
        (lambda: StatusBar("x\ny"), ValueError),
        (lambda: StatusBar(right=42), TypeError),
        (lambda: TextStyle(foreground=True), TypeError),
        (lambda: TextStyle(background=256), ValueError),
        (lambda: TextStyle(foreground=-1), ValueError),
        (lambda: TextStyle(bold=1), TypeError),
    ],
)
def test_invalid_widget_options_fail_without_evaluating_callbacks(factory, error):
    with pytest.raises(error):
        factory()


def test_invalid_dynamic_value_preserves_previous_label_snapshot():
    values = iter(["good", 42])
    label = Label(lambda: next(values))
    label.start()
    with pytest.raises(TypeError):
        label.update(0)
    assert label.text == "good"
    label.close()
