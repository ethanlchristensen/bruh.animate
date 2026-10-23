import json
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from bruhanimate import SnowSettings, cli, effect_registry
from bruhanimate.bruheffect.registry import EffectEntry


@pytest.mark.parametrize(
    "command, fragments",
    [
        (["list"], ["snow", "fire", "Falling snow"]),
        (["presets", "snow"], ["light", "moderate", "blizzard", "windy", "0.005"]),
        (
            ["info", "snow"],
            ["SnowSettings", "intensity: float", "min=0", "max=1", "wind"],
        ),
        (["info", "rain"], ["none", "east", "west", "0 is black"]),
        (["info", "static"], ["Settings: none", "No named presets"]),
    ],
)
def test_discovery_does_not_open_terminal(command, fragments, capsys, monkeypatch):
    run = Mock(side_effect=AssertionError("play called"))
    monkeypatch.setattr(cli, "play", run)
    assert cli.main(command) == 0
    output = capsys.readouterr().out
    for fragment in fragments:
        assert fragment in output
    run.assert_not_called()


def test_cli_preserves_preset_values_when_overriding(monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    assert (
        cli.main(
            [
                "play",
                "snow",
                "--preset",
                "light",
                "--set",
                "wind=0.5",
                "--set",
                "show_info=true",
                "--duration",
                "2.5",
                "--frames",
                "100",
                "--fps",
                "60",
                "--updates-per-second",
                "30",
            ]
        )
        == 0
    )
    run.assert_called_once_with(
        "snow",
        preset="light",
        settings=SnowSettings(intensity=0.005, wind=0.5, show_info=True),
        fps=60,
        updates_per_second=30,
        frames=100,
        duration=2.5,
        on_resize="raise",
    )
    assert effect_registry.presets("snow")["light"].wind == 0


def test_cli_json_tuple_and_string_options(monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    cli.main(["play", "matrix", "--set", "character_halt_range=[2,4]"])
    assert run.call_args.kwargs["settings"].character_halt_range == (2, 4)
    cli.main(["play", "rain", "--set", "wind_direction=east"])
    assert run.call_args.kwargs["settings"].wind_direction == "east"


def test_cli_seed_overrides_preset_and_settings(monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    cli.main(["play", "snow", "--preset", "light", "--set", "seed=3", "--seed", "42"])
    assert run.call_args.kwargs["settings"] == SnowSettings(intensity=0.005, seed=42)


def test_cli_records_without_terminal_and_protects_existing_files(
    tmp_path, monkeypatch, capsys
):
    from bruhanimate import Screen

    monkeypatch.setattr(
        Screen, "open", Mock(side_effect=AssertionError("terminal opened"))
    )
    output = tmp_path / "snow.cast"
    command = [
        "record",
        "snow",
        str(output),
        "--preset",
        "light",
        "--seed",
        "7",
        "--frames",
        "2",
        "--width",
        "8",
        "--height",
        "3",
    ]
    assert cli.main(command) == 0
    header = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert header == {"version": 2, "width": 8, "height": 3}
    original = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        cli.main(command)
    assert error.value.code == 2
    assert output.read_bytes() == original
    assert "error:" in capsys.readouterr().err
    assert cli.main([*command, "--overwrite"]) == 0
    assert output.read_bytes() == original


@pytest.mark.parametrize(
    "flags",
    [
        [],
        ["--duration", "-1"],
        ["--frames", "1", "--width", "0"],
        ["--frames", "1", "--seed", "-2"],
    ],
)
def test_cli_invalid_record_does_not_create_file(flags, tmp_path):
    output = tmp_path / "bad.cast"
    with pytest.raises(SystemExit):
        cli.main(["record", "snow", str(output), *flags])
    assert not output.exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ["play", "missing"],
        ["play", "snow", "--preset", "storm"],
        ["play", "snow", "--set", "wind=2"],
        ["play", "snow", "--set", "collision=1"],
        ["play", "snow", "--set", "typo=2"],
        ["play", "snow", "--set", "wind"],
        ["play", "snow", "--set", "wind=0", "--set", "wind=1"],
        ["play", "static", "--set", "wind=0"],
        ["play", "snow", "--duration", "nan"],
        ["play", "snow", "--duration", "-1"],
        ["play", "snow", "--fps", "0"],
        ["play", "snow", "--frames", "-1"],
        ["play", "snow", "--frames", "1.5"],
    ],
)
def test_cli_errors_are_actionable_and_do_not_play(arguments, monkeypatch, capsys):
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err
    run.assert_not_called()


def test_cli_discovers_runtime_registry_extensions(monkeypatch, capsys):
    @dataclass
    class CustomSettings:
        speed: int = 1

    constructor = Mock(side_effect=AssertionError("effect constructed"))
    monkeypatch.setitem(
        effect_registry._registry,
        "custom",
        EffectEntry(
            "custom",
            constructor,
            CustomSettings,
            "Custom animation",
            {"fast": CustomSettings(speed=3)},
        ),
    )
    cli.main(["list"])
    cli.main(["presets", "custom"])
    assert "speed=3" in capsys.readouterr().out
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    cli.main(["play", "custom", "--preset", "fast", "--duration", "0"])
    assert run.call_args.kwargs["settings"].speed == 3
    constructor.assert_not_called()


def test_cli_resize_policy(monkeypatch):
    run = Mock()
    monkeypatch.setattr(cli, "play", run)
    assert cli.main(["play", "snow", "--on-resize", "resize"]) == 0
    assert run.call_args.kwargs["on_resize"] == "resize"
    with pytest.raises(SystemExit):
        cli.main(["play", "snow", "--on-resize", "restart"])
