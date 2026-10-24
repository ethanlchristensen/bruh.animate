from importlib import import_module

import pytest
from test_player import Clock, RecordingScreen
from test_resize import ResizingScreen

import bruhanimate
from bruhanimate import AudioEffect, Player, Screen


@pytest.mark.parametrize("name", bruhanimate.__valid_demos__)
@pytest.mark.parametrize("size", [(24, 80), (3, 5), (1, 1)])
def test_every_demo_plays_and_restores_screen(name, size, monkeypatch):
    screen, clock = RecordingScreen(), Clock()
    screen.height, screen.width = size
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    original_run = Player.run

    def run(player):
        player.clock, player.sleep = clock, clock.sleep
        return original_run(player)

    monkeypatch.setattr(Player, "run", run)
    demo = import_module("bruhanimate.demos." + name)
    assert demo.run(frames=12) == 12
    assert screen.closed
    assert screen.batches == 12


@pytest.mark.parametrize("name", ["automaton", "diffusion"])
def test_showcases_reach_every_configuration(name, monkeypatch):
    from bruhanimate import Buffer

    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    showcase = import_module(f"bruhanimate.demos.{name}_demo").build(Buffer(3, 5))
    showcase.duration = 1 / 30
    clock = Clock()
    Player(
        RecordingScreen(),
        showcase,
        frames=len(showcase.phases),
        fps=30,
        clock=clock,
        sleep=clock.sleep,
    ).run()
    assert showcase.index == len(showcase.phases) - 1
    assert all(not effect._started for _, effect in showcase.phases)


@pytest.mark.parametrize("name", bruhanimate.__valid_demos__)
def test_every_demo_defaults_to_live_resize(name, monkeypatch):
    screen = ResizingScreen({1: (1, 1), 2: (45, 16), 4: (80, 24)})
    clock = Clock()
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    original_run = Player.run

    def run(player):
        assert player.on_resize == "resize"
        player.clock, player.sleep = clock, clock.sleep
        return original_run(player)

    monkeypatch.setattr(Player, "run", run)
    demo = import_module("bruhanimate.demos." + name)
    assert demo.run(frames=8) == 8
    assert screen.refreshes == 3
    assert screen.closed
    for width, height, writes in screen.presentations:
        assert all(0 <= x < width and 0 <= y < height for x, y, _ in writes)


@pytest.mark.parametrize("name", ["automaton", "diffusion"])
def test_showcase_resizes_inactive_phases_before_they_start(name, monkeypatch):
    from bruhanimate import Buffer

    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    showcase = import_module(f"bruhanimate.demos.{name}_demo").build(Buffer(3, 5))
    showcase.duration = 1 / 30
    screen = ResizingScreen({1: (12, 6), 2: (1, 1)})
    clock = Clock()
    assert (
        Player(
            screen,
            showcase,
            frames=len(showcase.phases) + 3,
            fps=30,
            on_resize="resize",
            clock=clock,
            sleep=clock.sleep,
        ).run()
        == len(showcase.phases) + 3
    )
    assert screen.refreshes == 2
    assert all(effect._viewport == (1, 1) for _, effect in showcase.phases)
    assert all(not effect._started for _, effect in showcase.phases)


@pytest.mark.parametrize("name", bruhanimate.__valid_demos__)
def test_demo_resize_can_explicitly_keep_raise_policy(name, monkeypatch):
    from bruhanimate.bruhutil.bruherrors import ScreenResizedError

    screen = ResizingScreen({0: (12, 6)})
    monkeypatch.setattr(Screen, "open", classmethod(lambda cls: screen))
    monkeypatch.setattr(AudioEffect, "_capture_loop", lambda self: None)
    demo = import_module("bruhanimate.demos." + name)
    with pytest.raises(ScreenResizedError):
        demo.run(frames=2, on_resize="raise")
    assert screen.closed
