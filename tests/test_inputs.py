from unittest.mock import Mock

import pytest

from bruhanimate import (
    Buffer,
    Button,
    Checkbox,
    Column,
    EventResult,
    Fixed,
    FocusGroup,
    FocusStack,
    FocusTarget,
    KeyBinding,
    KeyBindings,
    Panel,
    Slot,
    TextInput,
)


def test_text_edit_navigation_submit_and_printable_quit_keys():
    changes, submitted = [], []
    field = TextInput(
        "name", "ac", on_change=changes.append, on_submit=submitted.append
    )
    group = FocusGroup(field.focus)
    field.start()
    try:
        group.handle_event(-203)  # left
        assert not group.handle_event(ord("b"))
        assert (field.value, field.cursor) == ("abc", 2)
        group.handle_event(-200)  # home
        group.handle_event(-102)  # delete
        assert field.value == "bc"
        group.handle_event(-201)
        group.handle_event(127)  # normalized backspace
        assert field.value == "b"
        group.handle_event(ord("q"))
        group.handle_event(ord(" "))
        group.handle_event(13)  # normalized Enter
        assert field.value == "bq " and submitted == ["bq "]
        assert changes == ["abc", "bc", "b", "bq", "bq "]
        assert group.handle_event(27)  # scope default Escape quits
    finally:
        field.close()


@pytest.mark.parametrize("code", [ord("界"), ord("\u0301"), 0, 0x110000, -999])
def test_unsupported_text_events_do_not_insert(code):
    field = TextInput("text", "X")
    group = FocusGroup(field.focus, global_bindings=KeyBindings())
    field.start()
    assert group.dispatch(code) is EventResult.UNHANDLED
    assert field.value == "X"
    field.close()


def test_max_length_consumes_printables_and_programmatic_assignment_is_atomic():
    changed = Mock()
    field = TextInput("text", "ab", max_length=2, on_change=changed)
    group = FocusGroup(field.focus)
    field.start()
    assert not group.handle_event(ord("q"))
    assert field.value == "ab"
    for value in ("abc", "\n", "\x1b[31mx", "界"):
        with pytest.raises(ValueError):
            field.value = value
        assert field.value == "ab" and field.cursor == 2
    changed.assert_not_called()
    field.value = "Z"
    assert field.cursor == 1
    changed.assert_called_once_with("Z")
    field.value = "Z"
    changed.assert_called_once()
    field.close()


def test_draw_is_pure_scrolls_caret_and_preserves_old_frame_after_resize():
    changed = Mock()
    field = TextInput("text", "abcdef", on_change=changed)
    group = FocusGroup(field.focus)
    field.start()
    first, second = Buffer(1, 4), Buffer(1, 4)
    field.draw(first)
    field.draw(second)
    assert first.buffer == second.buffer == [list("def|")]
    assert field.cursor == 6
    field.resize((1, 1))
    tiny = Buffer(1, 1)
    field.draw(tiny)
    assert tiny.buffer == [["|"]]
    assert field.cursor == 6 and first.buffer == [list("def|")]
    changed.assert_not_called()
    group.handle_event(-200)
    field.draw(second)
    assert second.buffer == [list("|abc")]
    field.close()


def test_checkbox_and_button_only_activate_on_space_enter():
    changed, pressed = Mock(), Mock(return_value=None)
    check = Checkbox("check", "Enabled", on_change=changed)
    button = Button("button", "Apply", pressed)
    group = FocusGroup(check.focus, button.focus)
    check.start()
    button.start()
    for control in (check, button):
        control.update(1)
        control.draw(Buffer(1, 20))
    changed.assert_not_called()
    pressed.assert_not_called()
    group.handle_event(32)
    assert check.checked
    changed.assert_called_once_with(True)
    group.handle_event(9)
    group.handle_event(10)
    pressed.assert_called_once()
    assert group.dispatch(-203) is EventResult.UNHANDLED
    with pytest.raises(TypeError):
        check.checked = 1
    assert check.checked
    check.close()
    button.close()


def test_intrinsic_focus_lifecycle_and_parent_visibility():
    field = TextInput("text")
    button = Button("apply", "Apply", lambda: None)
    group = FocusGroup(field.focus, button.focus)
    layout = Column(Slot(field, size=Fixed(1)), Slot(button, size=Fixed(1))).build(
        Buffer(2, 12)
    )
    assert group.focused is None
    layout.start()
    assert group.focused is field.focus
    field.enabled = False
    assert group.focused is button.focus
    layout.set_visible(False)
    layout.resize((20, 3))
    assert group.focused is None
    layout.set_visible(True)
    assert group.focused is button.focus
    field.enabled = True
    assert group.focused is button.focus
    layout.close()
    assert group.focused is None
    field.close()
    with pytest.raises(RuntimeError):
        field.start()


def test_control_target_cannot_be_owned_by_a_panel_too():
    field = TextInput("text")
    with pytest.raises(ValueError):
        Panel(field, size=(10, 1), focus=field.focus)
    field.close()


def test_nested_modals_block_background_globals_and_restore_focus():
    calls = []
    a, b, c = (
        Button(name, name, lambda name=name: calls.append(name)) for name in "abc"
    )
    base = FocusGroup(
        a.focus,
        global_bindings=KeyBindings(
            KeyBinding.character("g", lambda: calls.append("global"))
        ),
    )
    modal = FocusGroup(b.focus, global_bindings=KeyBindings())
    nested = FocusGroup(c.focus, global_bindings=KeyBindings())
    router = FocusStack(base)
    for control in (a, b, c):
        control.start()
    router.push(modal)
    assert base.focused is None and not a.focus.focused
    assert not base.focus("a")
    assert base.dispatch(ord("g")) is EventResult.UNHANDLED
    assert router.dispatch(ord("g")) is EventResult.HANDLED
    router.handle_event(32)
    router.push(nested)
    assert modal.focused is None
    router.handle_event(32)
    c.set_visible(False)
    assert router.pop() is nested
    assert modal.focused is b.focus
    b.set_visible(False)
    router.pop()
    assert base.focused is a.focus
    router.handle_event(ord("g"))
    assert calls == ["b", "c", "global"]
    router.close()
    for control in (a, b, c):
        control.close()


def test_restore_falls_back_if_previous_target_becomes_unavailable():
    a, b = Button("a", "A", lambda: None), Button("b", "B", lambda: None)
    base = FocusGroup(a.focus, b.focus)
    a.start()
    b.start()
    router = FocusStack(base)
    router.push(FocusGroup(global_bindings=KeyBindings()))
    a.close()
    assert router.dispatch(ord("q")) is EventResult.HANDLED
    router.pop()
    assert base.focused is b.focus
    router.close()
    b.close()


def test_stack_ownership_root_protection_and_close_release_groups():
    base, modal = FocusGroup(), FocusGroup()
    router = FocusStack(base)
    with pytest.raises(ValueError):
        FocusStack(base)
    with pytest.raises(RuntimeError):
        router.pop()
    with pytest.raises(ValueError):
        router.push(base)
    router.push(modal)
    with pytest.raises(ValueError):
        router.push(modal)
    router.close()
    router.close()
    assert router.active is None and router.depth == 0
    with pytest.raises(RuntimeError):
        router.dispatch(32)
    replacement = FocusStack(base)
    replacement.push(modal)
    replacement.close()


def test_local_handler_validation_and_binding_priority():
    handler = Mock(return_value=EventResult.HANDLED)
    target = FocusTarget(
        "target", KeyBindings(KeyBinding("space", lambda: None)), handler=handler
    )
    panel = Panel(TextInput("inner"), size=(5, 1), focus=target)
    group = FocusGroup(target)
    panel.start()
    group.handle_event(32)
    handler.assert_not_called()
    group.handle_event(ord("x"))
    handler.assert_called_once_with(ord("x"))
    handler.return_value = True
    with pytest.raises(TypeError, match="EventResult"):
        group.dispatch(ord("y"))
    panel.close()


def test_handler_opening_modal_cannot_fall_through_to_background_global():
    from bruhanimate import Label

    global_action = Mock(return_value=None)
    modal = FocusGroup(global_bindings=KeyBindings())

    def open_modal(event):
        router.push(modal)
        return EventResult.UNHANDLED

    target = FocusTarget("root", KeyBindings(), handler=open_modal)
    root = FocusGroup(
        target, global_bindings=KeyBindings(KeyBinding.character("x", global_action))
    )
    router = FocusStack(root)
    panel = Panel(Label("root"), size=(5, 1), focus=target)
    panel.start()
    try:
        assert router.dispatch(ord("x")) is EventResult.HANDLED
        global_action.assert_not_called()
        assert router.active is modal
    finally:
        panel.close()
        router.close()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: TextInput("x", max_length=-1),
        lambda: TextInput("x", "bad\ntext"),
        lambda: TextInput("x", on_submit=1),
        lambda: Checkbox("x", "x", checked=1),
        lambda: Button("x", "x", None),
        lambda: TextInput("x", style="bad"),
        lambda: FocusTarget("x", KeyBindings(), handler=1),
        lambda: FocusStack(object()),
    ],
)
def test_invalid_input_options_fail_at_construction(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()
