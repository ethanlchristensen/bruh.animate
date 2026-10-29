import pytest

from bruhanimate import Buffer, ObjectGroup


class Child:
    def __init__(self, name, calls, *, fail=None, start=None, update=None):
        self.name, self.calls, self.fail = name, calls, fail
        self.on_start, self.on_update = start, update

    def note(self, method, *args):
        self.calls.append((self.name, method, *args))
        if method == self.fail:
            raise RuntimeError(f"{method} failed")

    def start(self):
        self.note("start")
        if self.on_start:
            self.on_start()

    def update(self, dt):
        self.note("update", dt)
        if self.on_update:
            self.on_update()

    def draw(self, buffer):
        self.note("draw")
        buffer.put_char(0, 0, self.name)

    def resize(self, size):
        self.note("resize", size)

    def set_visible(self, visible):
        self.note("visible", visible)

    def close(self):
        self.note("close")


def test_membership_is_queued_and_reordering_does_not_change_cleanup_order():
    calls = []
    a, b = Child("A", calls), Child("B", calls)
    group = ObjectGroup({"a": a, "b": b})
    assert not calls and group.names == ()
    group.start()
    group.start()
    assert group.names == ("a", "b")
    group.move_to_end("a")
    assert group.names == ("a", "b")
    group.update(0.5)
    assert group.names == ("b", "a") and group.get("a") is a
    assert [call for call in calls if call[1] == "update"] == [
        ("B", "update", 0.5),
        ("A", "update", 0.5),
    ]
    group.close()
    group.close()
    assert [call for call in calls if call[1] == "close"] == [
        ("B", "close"),
        ("A", "close"),
    ]


def test_changes_during_update_take_effect_on_next_update():
    calls = []
    group = ObjectGroup()
    b = Child("B", calls)

    def replace():
        group.remove("a")
        group.add("b", b)

    group.add("a", Child("A", calls, update=replace))
    group.start()
    group.update(0.25)
    assert group.names == ("a",)
    assert not any(call[0] == "B" for call in calls)
    group.update(0.5)
    assert group.names == ("b",)
    assert calls.index(("A", "close")) < calls.index(("B", "start"))
    assert ("B", "update", 0.5) in calls
    group.close()


def test_commands_from_start_are_deferred_and_receive_latest_viewport_visibility():
    calls = []
    group = ObjectGroup()
    b = Child("B", calls)
    group.add("a", Child("A", calls, start=lambda: group.add("b", b)))
    group.resize((10, 4))
    group.set_visible(False)
    group.start()
    assert group.names == ("a",)
    group.resize((5, 2))
    group.update(0)
    assert [call for call in calls if call[0] == "B"] == [
        ("B", "resize", (5, 2)),
        ("B", "visible", False),
        ("B", "start"),
        ("B", "update", 0),
    ]
    buffer = Buffer(2, 5)
    group.draw(buffer)
    assert buffer.get_char(0, 0) == " "
    group.set_visible(True)
    group.draw(buffer)
    assert buffer.get_char(0, 0) == "B"
    group.close()


@pytest.mark.parametrize("failure", ["resize", "visible", "start"])
def test_partial_application_failure_closes_all_owned_children_once(failure):
    calls = []
    group = ObjectGroup(
        {
            name: Child(name, calls, fail=failure if name == "B" else None)
            for name in "ABC"
        }
    )
    group.resize((3, 2))
    with pytest.raises(RuntimeError, match="failed"):
        group.start()
    group.close()
    assert [call for call in calls if call[1] == "close"] == [
        ("C", "close"),
        ("B", "close"),
        ("A", "close"),
    ]
    assert ("C", "start") not in calls
    assert group.names == ()
    with pytest.raises(RuntimeError):
        group.start()


def test_removal_failure_closes_remaining_and_pending_children():
    calls = []
    group = ObjectGroup({"a": Child("A", calls, fail="close"), "b": Child("B", calls)})
    group.start()
    group.remove("a")
    group.add("c", Child("C", calls))
    with pytest.raises(RuntimeError, match="close failed"):
        group.update(0)
    group.close()
    assert [call for call in calls if call[1] == "close"] == [
        ("A", "close"),
        ("C", "close"),
        ("B", "close"),
    ]


def test_close_before_start_and_close_errors_release_every_child():
    calls = []
    group = ObjectGroup({"a": Child("A", calls), "b": Child("B", calls, fail="close")})
    with pytest.raises(RuntimeError):
        group.close()
    group.close()
    assert calls == [("B", "close"), ("A", "close")]


def test_queued_remove_then_replacement_preserves_identity_and_closes_old_child():
    calls = []
    a, b = Child("A", calls), Child("B", calls)
    group = ObjectGroup({"same": a})
    group.start()
    group.remove("same")
    group.add("same", b)
    assert group.get("same") is a
    group.update(0)
    assert group.get("same") is b
    assert calls.count(("A", "close")) == 1
    group.close()
    assert calls.count(("A", "close")) == 1


def test_validation_is_atomic_and_considers_pending_ownership():
    calls = []
    a = Child("A", calls)
    group = ObjectGroup({"a": a})
    with pytest.raises(ValueError):
        group.add("a", Child("B", calls))
    with pytest.raises(ValueError):
        group.add("b", a)
    group.remove("a")
    with pytest.raises(ValueError):
        group.add("b", a)
    with pytest.raises(ValueError):
        group.add("self", group)
    with pytest.raises(TypeError):
        group.add("bad", object())
    with pytest.raises(KeyError):
        group.remove("missing")
    group.close()
    assert calls == [("A", "close")]


def test_group_is_endless_and_requires_start_for_updates():
    group = ObjectGroup()
    assert group.finished is None
    with pytest.raises(RuntimeError):
        group.update(0)
    group.start()
    group.update(100)
    with pytest.raises(ValueError):
        group.update(-1)
    assert group.finished is None
    group.close()


def test_demo_spawns_removes_and_keeps_membership_bounded_across_resize():
    from bruhanimate.demos.objects_demo import build

    demo = build(Buffer(12, 40))
    demo.start()
    membership = set()
    try:
        for index in range(150):
            if index == 50:
                demo.resize((1, 1))
            demo.update(1 / 30)
            membership.add("spark" in demo.group.names)
            demo.draw(Buffer(1, 1))
            assert len(demo.group.names) <= 5
        assert membership == {True, False}
    finally:
        demo.close()


def test_drawing_is_isolated_and_snapshots_mutable_cells():
    from bruhanimate import CallbackEffect

    class Cell:
        value = "X"

        def __str__(self):
            return self.value

    cell = Cell()
    observed = []

    def overlay(buffer):
        observed.append(buffer.get_char(1, 0))
        buffer.put_char(0, 0, cell)

    group = ObjectGroup(
        {
            "base": CallbackEffect(lambda b: b.put_at(0, 0, "ABC")),
            "overlay": CallbackEffect(overlay),
        }
    )
    group.start()
    first, second = Buffer(1, 3), Buffer(1, 3)
    group.draw(first)
    group.draw(second)
    assert observed == [None, None]
    assert first.buffer == second.buffer == [list("XBC")]
    cell.value = "Y"
    group.resize((1, 1))
    group.draw(Buffer(1, 1))
    assert first.buffer == [list("XBC")]
    group.close()
