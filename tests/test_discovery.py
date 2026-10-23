"""The typed catalog must stay aligned with the live registry."""

from typing import get_args
from unittest.mock import Mock

import pytest

from bruhanimate import EffectName, SnowSettings, effect_registry, effects


def test_catalog_names_and_preset_literals_match_registry():
    assert set(get_args(EffectName)) == set(effect_registry.names())
    for name in effect_registry.names():
        info = getattr(effects, name)
        assert isinstance(info, effects.EffectInfo)
        assert info.name == name
        assert info.description == effect_registry.get(name).description
        # The static declaration is what editors use; detect stale preset hints.
        from typing import get_type_hints

        settings_type, preset_type = get_args(get_type_hints(effects)[name])
        assert set(get_args(preset_type)) == set(info.presets())
        default = info.defaults()
        assert (
            default is None
            if settings_type is type(None)
            else isinstance(default, settings_type)
        )


def test_discovery_copies_mutable_presets_and_typed_defaults():
    first = effects.twinkle.preset("sparse")
    first.twinkle_chars.append("X")
    assert effects.twinkle.preset("sparse").twinkle_chars == ["."]
    presets = effect_registry.presets("twinkle")
    presets["sparse"].twinkle_chars.clear()
    assert effect_registry.presets("twinkle")["sparse"].twinkle_chars == ["."]
    assert effects.snow.preset("light") == SnowSettings(intensity=0.005)
    assert effects.snow.defaults() == SnowSettings()
    assert effects.snow.defaults() is not effects.snow.defaults()


def test_typed_play_forwards_to_shared_player(monkeypatch):
    from bruhanimate import player

    run = Mock(return_value=42)
    monkeypatch.setattr(player, "play", run)
    assert effects.snow.play(preset="light", duration=2, fps=60) == 42
    assert run.call_args.args == ("snow",)
    assert run.call_args.kwargs["preset"] == "light"
    assert run.call_args.kwargs["duration"] == 2
    assert run.call_args.kwargs["fps"] == 60


def test_unknown_preset_explains_available_choices():
    with pytest.raises(KeyError, match="blizzard.*light.*moderate.*windy"):
        effects.snow.preset("missing")
