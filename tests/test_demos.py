from importlib import import_module

import pytest
from test_player import Clock, RecordingScreen

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


@pytest.mark.parametrize("name", ["audio", "automaton", "diffusion"])
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
