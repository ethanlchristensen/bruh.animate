import pytest

from bruhanimate import Buffer
from bruhanimate.demos.topdown_demo import STARS, TopDownGame


def step(game, key):
    assert not game.handle_event(ord(key))
    game.update(1 / 12)


def test_commands_wait_for_update_and_draw_does_not_consume_input():
    game = TopDownGame()
    game.start()
    try:
        game.handle_event(ord("d"))
        first, second = Buffer(14, 40), Buffer(14, 40)
        game.draw(first)
        game.draw(second)
        assert first.buffer == second.buffer
        assert game.position == (2, 2)
        game.update(1 / 12)
        assert game.position == (3, 2)
        game.draw(second)
        assert first.buffer != second.buffer
    finally:
        game.close()


def test_game_collects_stars_blocks_walls_pauses_and_resets():
    game = TopDownGame()
    game.start()
    try:
        for key in "ddds":
            step(game, key)
        assert game.position == (5, 3) and len(game.remaining) == 4
        step(game, "p")
        state = game.position, game.hero.frame_index
        for key in "dddd":
            step(game, key)
        assert (game.position, game.hero.frame_index) == state
        step(game, "p")
        for key in "d" * 20:
            step(game, key)
        assert game.position == (11, 3)  # first wall, no tunneling
        step(game, "r")
        assert game.position == (2, 2) and game.remaining == set(STARS)
        assert not game.paused
        assert game.handle_event(ord("q"))
        assert game.handle_event(27)
    finally:
        game.close()


def test_queue_is_bounded_and_one_command_is_consumed_per_tick():
    game = TopDownGame()
    game.start()
    try:
        for key in "ds" * 100:
            game.handle_event(ord(key))
        assert len(game._commands) == 16
        game.update(100)
        assert game.position == (3, 2) and len(game._commands) == 15
    finally:
        game.close()


def test_recorded_event_ticks_replay_identically_across_resize():
    first, second = TopDownGame((25, 10)), TopDownGame((60, 20))
    first.start()
    second.start()
    try:
        for index, key in enumerate("dddssddddddddssssddppasddrds"):
            step(first, key)
            step(second, key)
            if index == 10:
                first.resize((1, 1))
            assert first.position == second.position
            assert first.remaining == second.remaining
            assert first.paused == second.paused
            assert first.hero.frame_index == second.hero.frame_index
            first.draw(Buffer(1, 1))
    finally:
        first.close()
        second.close()


def test_closed_and_unstarted_game_lifecycle():
    game = TopDownGame()
    with pytest.raises(RuntimeError):
        game.update(0)
    game.close()
    game.close()
    game.handle_event(ord("d"))
    assert not game._commands
    with pytest.raises(RuntimeError):
        game.start()
    game.draw(Buffer(1, 1))


def test_all_collectibles_have_walkable_routes():
    from collections import deque

    game = TopDownGame()
    queue, reachable = deque([game.position]), {game.position}
    while queue:
        point = queue.popleft()
        for delta in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            neighbor = game.world.move((*point, 1, 1), delta)
            if neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    assert STARS <= reachable
    game.close()


def test_interactive_entrypoint_routes_keys_through_player_and_restores_screen(
    monkeypatch,
):
    from test_player import Clock, RecordingScreen

    from bruhanimate import Player, Screen
    from bruhanimate.demos import topdown_demo

    screen, clock = RecordingScreen([ord("d"), ord("s")]), Clock()
    created = []
    original_build, original_run = topdown_demo.build, Player.run

    def build(buffer):
        game = original_build(buffer)
        created.append(game)
        return game

    def run(player):
        player.clock, player.sleep = clock, clock.sleep
        return original_run(player)

    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(topdown_demo, "build", build)
    monkeypatch.setattr(Player, "run", run)
    assert topdown_demo.run(frames=3, fps=12) == 3
    assert created[0].position == (3, 3)
    assert created[0]._closed and screen.closed
