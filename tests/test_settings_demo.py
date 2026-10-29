import pytest

from bruhanimate import Buffer
from bruhanimate.demos.settings_demo import build


def test_modal_edit_apply_cancel_and_background_shortcut_isolation():
    demo = build(Buffer(24, 70))
    demo.start()
    try:
        assert demo.root_scope.focused is demo.edit.focus
        assert not demo.handle_event(ord("e"))
        assert demo.modal_open and demo.focus.depth == 2
        assert demo.root_scope.focused is None
        demo.name_input.value = ""
        for char in "quiet":
            assert not demo.handle_event(ord(char))
        assert demo.name_input.value == "quiet"
        demo.handle_event(9)
        assert demo.modal_scope.focused is demo.effects.focus
        demo.handle_event(ord("b"))
        assert demo.background_actions == 0
        demo.handle_event(32)
        assert not demo.effects.checked
        demo.handle_event(9)
        demo.handle_event(10)
        assert demo.name == "quiet" and not demo.effects_enabled
        assert not demo.modal_open and demo.root_scope.focused is demo.edit.focus
        demo.handle_event(ord("b"))
        assert demo.background_actions == 1
        demo.open_modal()
        demo.name_input.value = "discard me"
        assert not demo.handle_event(27)
        assert demo.name == "quiet" and not demo.modal_open
        demo.open_modal()
        assert demo.name_input.value == "quiet"
        assert demo.handle_event(3)  # explicit modal Ctrl+C exit
    finally:
        demo.close()


def test_validation_and_resize_retain_draft_without_exposing_background():
    demo = build(Buffer(24, 70))
    demo.start()
    try:
        demo.open_modal()
        demo.name_input.value = "  "
        demo.handle_event(10)
        assert demo.modal_open and demo.message
        assert demo.name == "Explorer"
        demo.name_input.value = "Draft"
        demo.handle_event(-203)
        cursor = demo.name_input.cursor
        demo.resize((1, 1))
        assert demo.name_input.value == "Draft" and demo.name_input.cursor == cursor
        assert demo.root_scope.focused is None
        assert demo.modal_scope.focused is None
        demo.draw(Buffer(1, 1))
        demo.resize((70, 24))
        assert demo.modal_scope.focused is demo.name_input.focus
        assert demo.name_input.cursor == cursor
        demo.set_visible(False)
        demo.resize((60, 22))
        assert demo.modal_scope.focused is None
        demo.set_visible(True)
        assert demo.modal_scope.focused is demo.name_input.focus
        demo.handle_event(27)
        assert not demo.modal_open
    finally:
        demo.close()


def test_modal_draws_are_pure_and_do_not_apply_drafts():
    demo = build(Buffer(24, 70))
    demo.start()
    try:
        demo.open_modal()
        demo.name_input.value = "New"
        demo.update(0)
        first, second = Buffer(24, 70), Buffer(24, 70)
        demo.draw(first)
        demo.draw(second)
        assert first.buffer == second.buffer
        visible = "\n".join("".join(row) for row in first.buffer)
        assert "Background action" not in visible
        assert demo.name == "Explorer" and demo.name_input.cursor == 3
        demo.handle_event(ord("x"))
        demo.draw(second)
        assert first.buffer != second.buffer
    finally:
        demo.close()


def test_settings_demo_player_input_and_cleanup(monkeypatch):
    from test_player import Clock, RecordingScreen

    from bruhanimate import Player, Screen
    from bruhanimate.demos import settings_demo

    screen, clock = RecordingScreen([ord("e"), ord("q"), 27, None]), Clock()
    screen.width, screen.height = 70, 24
    created = []
    original_build, original_run = settings_demo.build, Player.run

    def factory(buffer):
        demo = original_build(buffer)
        created.append(demo)
        return demo

    def run(player):
        player.clock, player.sleep = clock, clock.sleep
        return original_run(player)

    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(settings_demo, "build", factory)
    monkeypatch.setattr(Player, "run", run)
    assert settings_demo.run(frames=3) == 3  # q typed into the modal did not quit
    assert created[0].name == "Explorer"
    assert created[0]._closed and screen.closed
    assert not created[0].name_input.focus.available


def test_close_before_start_is_idempotent_and_releases_router():
    demo = build(Buffer(24, 70))
    demo.close()
    demo.close()
    assert demo.focus.depth == 0
    with pytest.raises(RuntimeError):
        demo.start()
