from unittest.mock import Mock

import pytest
from test_player import Clock, RecordingScreen

from bruhanimate import (
    BindingHint,
    Buffer,
    Column,
    EventResult,
    Fixed,
    FocusGroup,
    FocusTarget,
    KeyBinding,
    KeyBindings,
    Label,
    Panel,
    Player,
    Row,
    Scene,
    Slot,
    TimedOverlay,
)


def target(name, action=None, *, enabled=True):
    return FocusTarget(
        name,
        KeyBindings(KeyBinding("space", action or Mock(return_value=None))),
        enabled=enabled,
    )


def panel(item):
    return Panel(Label(item.name), size=(4, 2), focus=item, fit=True)


@pytest.mark.parametrize(
    "name, codes",
    [
        ("space", [32]),
        ("enter", [10, 13]),
        ("escape", [-1, 27]),
        ("tab", [-301, 9, 11]),
        ("shift+tab", [-302]),
        ("backspace", [-300, 8, 127]),
        ("left", [-203]),
        ("right", [-205]),
        ("up", [-204]),
        ("down", [-206]),
        ("home", [-200]),
        ("end", [-201]),
        ("insert", [-101]),
        ("delete", [-102]),
        ("page_up", [-207]),
        ("page_down", [-208]),
        ("ctrl+c", [3]),
        ("f1", [-2]),
        ("f12", [-13]),
    ],
)
def test_named_keys_and_legacy_aliases(name, codes):
    action = Mock(return_value=None)
    bindings = KeyBindings(KeyBinding(name, action, description="action"))
    action.assert_not_called()
    assert bindings.hints() == (BindingHint(name, "action"),)
    assert bindings.help_text() == f"{name} action"
    action.assert_not_called()
    for code in codes:
        assert bindings.dispatch(code) is EventResult.HANDLED
    assert action.call_count == len(codes)
    assert bindings.dispatch(ord("z")) is EventResult.UNHANDLED


def test_character_case_duplicate_keys_and_help_aliases():
    action = Mock(return_value=None)
    binding = KeyBinding.character("q", action, description="type q")
    bindings = KeyBindings(binding, KeyBinding("enter", action))
    assert bindings.bindings == (binding, bindings.bindings[1])
    assert bindings.dispatch(ord("Q")) is EventResult.UNHANDLED
    assert bindings.dispatch(ord("q")) is EventResult.HANDLED
    assert bindings.help_text() == "q type q"
    with pytest.raises(ValueError, match="Duplicate"):
        KeyBindings(KeyBinding("space", action), KeyBinding.character(" ", action))


def test_quit_adapter_is_explicit_and_rejects_boolean_action_results():
    bindings = KeyBindings(KeyBinding("enter", quit=True))
    assert bindings.dispatch(10) is EventResult.QUIT
    assert bindings.handle_event(10) is True
    assert bindings.handle_event(32) is False
    bad = KeyBindings(KeyBinding("space", lambda: False))
    with pytest.raises(TypeError, match="return None"):
        bad.handle_event(32)
    with pytest.raises(TypeError, match="handle_event"):
        bool(EventResult.UNHANDLED)


def test_focus_navigation_skip_disable_hide_close_and_wrap():
    a, b, c = target("a"), target("b", enabled=False), target("c")
    group = FocusGroup(a, b, c)
    panels = [panel(item) for item in (a, b, c)]
    assert group.focused is None and group.targets == (a, b, c)
    for view in panels:
        view.start()
    assert group.focused is a and a.focused
    assert not group.handle_event(9)
    assert group.focused is c and not a.focused
    group.move()
    assert group.focused is a
    group.move("previous")
    assert group.focused is c
    b.enabled = True
    assert group.focused is c  # Becoming available never steals selection.
    group.handle_event(-302)
    assert group.focused is b
    panels[1].set_visible(False)
    assert group.focused is c
    panels[2].close()
    assert group.focused is a
    assert group.focus("b") is False
    with pytest.raises(KeyError):
        group.focus("missing")
    panels[1].set_visible(True)
    assert group.focus("b") and group.focused is b
    for view in panels:
        view.close()
    assert group.focused is None and not any(t.focused for t in (a, b, c))
    assert group.handle_event(ord("q"))  # Quit still works with no available panel.


def test_focus_order_global_fallback_and_reserved_navigation():
    calls = []
    a = FocusTarget(
        "a",
        KeyBindings(
            KeyBinding.character("q", lambda: calls.append("local")),
            KeyBinding("tab", lambda: calls.append("tab local")),
        ),
    )
    b = target("b")
    group = FocusGroup(
        a,
        b,
        global_bindings=KeyBindings(
            KeyBinding.character("q", quit=True),
            KeyBinding.character("g", lambda: calls.append("global")),
        ),
    )
    views = [panel(a), panel(b)]
    for view in views:
        view.start()
    assert not group.handle_event(ord("q")) and calls == ["local"]
    assert group.dispatch(ord("g")) is EventResult.HANDLED
    assert calls == ["local", "global"]
    assert group.dispatch(ord("z")) is EventResult.UNHANDLED
    group.handle_event(9)
    assert group.focused is b and "tab local" not in calls
    assert group.handle_event(ord("q"))
    for view in views:
        view.close()


def test_navigation_without_wrap_and_custom_named_keys():
    a, b = target("a"), target("b")
    group = FocusGroup(a, b, next_key="down", previous_key="up", wrap=False)
    views = [panel(a), panel(b)]
    for view in views:
        view.start()
    group.move("previous")
    assert group.focused is a
    group.handle_event(-206)
    group.handle_event(-206)
    assert group.focused is b
    group.handle_event(-204)
    assert group.focused is a
    for view in views:
        view.close()


def test_nested_layout_visibility_reconciles_focus_across_zero_area_resize():
    a, b = target("solver"), target("signal")
    group = FocusGroup(a, b)
    views = [panel(a), panel(b)]
    layout = Column(Slot(Row(Slot(views[0]), Slot(views[1], size=Fixed(8))))).build(
        Buffer(5, 20)
    )
    layout.start()
    assert group.focused is a
    layout.resize((8, 5))
    assert not a.available and b.available and group.focused is b
    layout.resize((20, 5))
    assert a.available and group.focused is b
    layout.set_visible(False)
    assert group.focused is None
    layout.resize((30, 8))
    assert group.focused is None  # Hidden ancestors stay hidden during reflow.
    layout.set_visible(True)
    assert group.focused is a
    layout.close()
    assert group.focused is None


def test_initially_hidden_factory_is_not_focusable_until_first_start():
    item = target("late")
    group = FocusGroup(item)
    factory = Mock(side_effect=lambda b: panel(item))
    layout = Row(
        Slot(Label("fixed"), size=Fixed(6)), Slot(effect_factory=factory)
    ).build(Buffer(3, 6))
    layout.start()
    assert group.focused is None
    factory.assert_not_called()
    layout.resize((12, 5))
    assert group.focused is item
    factory.assert_called_once()
    layout.close()


def test_focus_border_draw_is_pure_and_does_not_mutate_old_frame():
    action = Mock(return_value=None)
    a, b = target("a", action), target("b")
    group = FocusGroup(a, b)
    first, second = panel(a), panel(b)
    first.start()
    second.start()
    old = Buffer(4, 6)
    first.draw(old)
    original = [row[:] for row in old.buffer]
    assert "\x1b[1m" in old.get_char(0, 0) and "38;5;226" in old.get_char(0, 0)
    group.focus("b")
    new = Buffer(4, 6)
    first.draw(new)
    assert new.get_char(0, 0) == "+" and old.buffer == original
    action.assert_not_called()
    first.close()
    second.close()


def test_failed_panel_start_and_overlay_expiry_remove_focus_without_double_cleanup():
    item = target("bad")
    group = FocusGroup(item)
    child = Label("x")
    child.start = Mock(side_effect=RuntimeError("failed"))
    child.close = Mock()
    view = Panel(child, size=(2, 1), focus=item)
    with pytest.raises(RuntimeError):
        view.start()
    view.close()
    assert group.focused is None
    child.close.assert_called_once()
    overlay = TimedOverlay(panel(item), duration=1, delay=1)
    scene = Scene(overlay)
    scene.start()
    assert group.focused is None
    scene.update(1)
    assert group.focused is item
    scene.update(1)
    assert group.focused is None
    scene.close()


def test_player_routes_handled_keys_without_quitting_and_keeps_existing_bool_handlers():
    action = Mock(return_value=None)
    item = target("one", action)
    group = FocusGroup(item)
    view = panel(item)
    clock = Clock()
    screen = RecordingScreen(events=[32, None, ord("q")])
    assert (
        Player(
            screen,
            view,
            event_handler=group.handle_event,
            clock=clock,
            sleep=clock.sleep,
        ).run()
        == 1
    )
    action.assert_called_once()
    assert group.focused is None
    assert (
        Player(
            RecordingScreen(events=[ord("x")]),
            Label("legacy"),
            event_handler=lambda event: True,
        ).run()
        == 0
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: KeyBinding("spaec", lambda: None),
        lambda: KeyBinding("space"),
        lambda: KeyBinding("space", 123),
        lambda: KeyBinding("space", quit="yes"),
        lambda: KeyBinding.character("qq", lambda: None),
        lambda: KeyBinding.character("\n", lambda: None),
        lambda: KeyBinding.character("界", lambda: None),
        lambda: KeyBinding("space", lambda: None, description="bad\nhelp"),
        lambda: KeyBindings("space"),
        lambda: FocusTarget("", KeyBindings()),
        lambda: FocusTarget("a", "bindings"),
        lambda: FocusTarget("a", KeyBindings(), enabled=1),
        lambda: FocusGroup(next_key="space", previous_key="space"),
        lambda: FocusGroup(next_key="typo"),
        lambda: FocusGroup(wrap="yes"),
        lambda: FocusGroup(global_bindings="keys"),
        lambda: FocusGroup("target"),
    ],
)
def test_invalid_options_fail_before_opening_resources(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_visibility_failure_during_start_still_closes_supplied_content():
    item = target("bad visibility")
    group = FocusGroup(item)
    child = Label("x")
    child.set_visible = Mock(side_effect=RuntimeError("visibility failed"))
    child.close = Mock()
    view = Panel(child, size=(4, 2), focus=item)
    with pytest.raises(RuntimeError, match="visibility failed"):
        view.start()
    view.close()
    child.close.assert_called_once()
    assert group.focused is None


def test_closed_panel_cannot_change_focus_of_replacement():
    item = target("reusable")
    group = FocusGroup(item)
    old = panel(item)
    old.close()
    replacement = panel(item)
    replacement.start()
    old.set_visible(False)
    old.close()
    assert group.focused is item and item.available
    replacement.close()


def test_target_duplicate_ownership_and_invalid_mutations():
    item = target("one")
    group = FocusGroup(item)
    with pytest.raises(ValueError):
        FocusGroup(item)
    with pytest.raises(ValueError):
        FocusGroup(target("same"), target("same"))
    view = panel(item)
    with pytest.raises(ValueError):
        panel(item)
    with pytest.raises(TypeError):
        item.enabled = 1
    with pytest.raises(ValueError):
        group.move("backwards")
    with pytest.raises(TypeError):
        group.dispatch(True)
    view.close()
