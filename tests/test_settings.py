from dataclasses import fields
from unittest.mock import Mock

import pytest

from bruhanimate import (
    AudioSettings,
    Buffer,
    EffectRegistry,
    MatrixSettings,
    NoiseEffect,
    NoiseSettings,
    OffsetSettings,
    PerlinSettings,
    RainSettings,
    SnowEffect,
    SnowSettings,
    TwinkleSettings,
    effect_registry,
    play,
)
from bruhanimate.bruheffect.settings import EffectSettings


@pytest.mark.parametrize(
    "entry", list(effect_registry.entries().values()), ids=lambda e: e.name
)
def test_every_builtin_settings_type_checks_fields_and_numeric_bounds(entry):
    if entry.settings_cls is None:
        return
    settings = entry.settings_cls()
    assert isinstance(settings, EffectSettings)
    settings.validate()
    for item in fields(settings):
        bad = entry.settings_cls()
        setattr(bad, item.name, object())
        with pytest.raises(TypeError, match=item.name):
            bad.validate()
        for bound, delta in (("min", -1), ("max", 1)):
            limit = item.metadata.get(bound)
            if limit is None:
                continue
            bad = entry.settings_cls()
            # Keep integer fields integer so this exercises range validation.
            setattr(bad, item.name, limit + delta)
            with pytest.raises(ValueError, match=item.name):
                bad.validate()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_settings_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        SnowSettings(intensity=value)


@pytest.mark.parametrize(
    "cls, options, error",
    [
        (SnowSettings, {"wind": 2}, ValueError),
        (SnowSettings, {"intensity": True}, TypeError),
        (SnowSettings, {"collision": 1}, TypeError),
        (RainSettings, {"wind_direction": "north"}, ValueError),
        (RainSettings, {"lightning_color_type": 256}, ValueError),
        (MatrixSettings, {"gradient_length": 0}, ValueError),
        (MatrixSettings, {"character_halt_range": (2, 1)}, ValueError),
        (MatrixSettings, {"color_halt_range": (0, 1)}, ValueError),
        (MatrixSettings, {"color_halt_range": (1,)}, ValueError),
        (MatrixSettings, {"color_halt_range": [1, 2]}, TypeError),
        (PerlinSettings, {"octaves": 0}, ValueError),
        (AudioSettings, {"mode": "typo"}, ValueError),
        (OffsetSettings, {"direction": "up"}, ValueError),
        (TwinkleSettings, {"twinkle_chars": []}, ValueError),
        (TwinkleSettings, {"twinkle_chars": ["XX"]}, ValueError),
        (TwinkleSettings, {"twinkle_chars": ["界"]}, ValueError),
        (TwinkleSettings, {"twinkle_chars": ["\u0301"]}, ValueError),
        (TwinkleSettings, {"twinkle_chars": ["\x1b"]}, ValueError),
    ],
)
def test_invalid_configuration_fails_at_construction(cls, options, error):
    with pytest.raises(error):
        cls(**options)


def test_zero_values_and_black_color_are_valid():
    assert RainSettings(intensity=0, lightning_color_type=0).lightning_color_type == 0
    assert SnowSettings(intensity=0, wind=0).intensity == 0
    effect = NoiseEffect(Buffer(2, 3), " ", NoiseSettings(intensity=0))
    effect.update(1 / 30)
    assert effect.buffer.buffer == [[" "] * 3 for _ in range(2)]


def test_wrong_settings_type_and_edited_settings_fail_before_effect_use():
    with pytest.raises(TypeError, match="SnowSettings"):
        SnowEffect(Buffer(2, 3), " ", RainSettings())
    settings = SnowSettings()
    settings.wind = 10
    with pytest.raises(ValueError, match="wind"):
        SnowEffect(Buffer(2, 3), " ", settings)
    with pytest.raises(ValueError, match="wind"):
        effect_registry.create("snow", Buffer(2, 3), " ", settings=settings)


def test_registry_rejects_unsupported_and_wrong_settings_without_constructing():
    registry = EffectRegistry()
    constructor = Mock()
    registry.register("custom", constructor, SnowSettings)
    registry.register("plain", constructor)
    with pytest.raises(TypeError, match="requires SnowSettings"):
        registry.create("custom", Buffer(1, 1), " ", settings=RainSettings())
    with pytest.raises(TypeError, match="does not accept"):
        registry.create("plain", Buffer(1, 1), " ", settings=SnowSettings())
    with pytest.raises(ValueError, match="background"):
        registry.create("plain", Buffer(1, 1), "")
    constructor.assert_not_called()


def test_invalid_preset_registration_is_atomic():
    registry = EffectRegistry()
    with pytest.raises(TypeError, match="SnowSettings"):
        registry.register(
            "custom", Mock(), SnowSettings, presets={"bad": RainSettings()}
        )
    assert "custom" not in registry


def test_explicit_settings_override_known_presets_but_typos_are_rejected():
    custom = SnowSettings(intensity=0)
    assert (
        effect_registry.resolve_settings("snow", preset="light", settings=custom)
        is custom
    )
    with pytest.raises(KeyError, match="missing"):
        effect_registry.resolve_settings("snow", preset="missing", settings=custom)


def test_play_validates_named_settings_before_opening_terminal(monkeypatch):
    from bruhanimate import Screen

    open_screen = Mock(side_effect=AssertionError("terminal opened"))
    monkeypatch.setattr(Screen, "show", open_screen)
    with pytest.raises(TypeError, match="SnowSettings"):
        play("snow", settings=RainSettings())
    with pytest.raises(KeyError, match="missing"):
        play("snow", preset="missing")
    open_screen.assert_not_called()
