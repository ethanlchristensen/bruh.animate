"""Versioned, data-only effect configurations; loading never starts an effect."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, get_origin, get_type_hints

from ._validation import _seconds
from .bruheffect.registry import EffectEntry, effect_registry
from .resize import _size


@dataclass
class EffectConfig:
    """Portable settings plus playback/capture options, in seconds and cells.

    Settings are copied and validated on save/load. JSON schema version 1 stores
    resolved dataclass settings, so a named preset changing does not change saved
    values. Only registered names are accepted; files never import or execute code.
    A None seed retains the effect's normal random behavior. Custom registry
    entries must be registered by the application before loading their files.
    """

    effect: str
    settings: object | None = None
    fps: float = 30
    updates_per_second: float | None = None
    frames: int | None = None
    duration: float | None = None
    width: int = 80
    height: int = 24

    def validate(self) -> None:
        effect_registry.resolve_settings(self.effect, settings=self.settings)
        for name in ("fps", "updates_per_second"):
            value = getattr(self, name)
            if value is None and name == "updates_per_second":
                continue
            _seconds(value, name)
            if value == 0:
                raise ValueError(f"{name} must be positive")
        if self.frames is not None:
            if type(self.frames) is not int:
                raise TypeError("frames must be an integer or None")
            if self.frames < 0:
                raise ValueError("frames must be non-negative")
        if self.duration is not None:
            _seconds(self.duration, "duration")
        _size((self.width, self.height))

    def save(self, path: str | os.PathLike[str], *, overwrite: bool = False) -> Path:
        """Atomically save JSON; parent must exist, existing files are protected."""
        self.validate()
        if type(overwrite) is not bool:
            raise TypeError("overwrite must be a bool")
        cls = effect_registry.get(self.effect).settings_cls
        settings = (
            self.settings if self.settings is not None else cls() if cls else None
        )
        if settings is not None and (
            not is_dataclass(settings) or isinstance(settings, type)
        ):
            raise TypeError("Saved presets require dataclass settings")
        data = {item.name: getattr(self, item.name) for item in fields(self)}
        data["settings"] = asdict(settings) if settings is not None else None
        payload = (
            json.dumps({"schema_version": 1, **data}, indent=2, allow_nan=False) + "\n"
        )
        destination = Path(path).absolute()
        if not overwrite and destination.exists():
            raise FileExistsError(destination)
        with NamedTemporaryFile(
            dir=destination.parent, prefix=".bruhanimate-preset-", delete=False
        ) as stream:
            temporary = Path(stream.name)
        try:
            temporary.write_text(payload, encoding="utf-8")
            if overwrite:
                os.replace(temporary, destination)
            elif os.name == "nt":
                os.rename(temporary, destination)
            else:
                os.link(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> EffectConfig:
        """Load and validate a JSON configuration without constructing content."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Preset must be a JSON object")
        if (
            type(data.get("schema_version")) is not int
            or data.pop("schema_version") != 1
        ):
            raise ValueError("Unsupported preset schema_version (expected 1)")
        unknown = data.keys() - {item.name for item in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown preset fields: {', '.join(sorted(unknown))}")
        if not isinstance(data.get("effect"), str):
            raise ValueError("Preset requires an effect name")
        entry = effect_registry.get(data["effect"])
        values = data.get("settings")
        if values is not None:
            if (
                not isinstance(values, dict)
                or entry.settings_cls is None
                or not is_dataclass(entry.settings_cls)
            ):
                raise TypeError("Preset settings must be a dataclass field object")
            hints = get_type_hints(entry.settings_cls)
            converted: dict[str, Any] = {}
            for key, value in values.items():
                if key not in {item.name for item in fields(entry.settings_cls)}:
                    raise ValueError(f"Unknown setting: {key}")
                converted[key] = (
                    tuple(value)
                    if get_origin(hints.get(key)) is tuple and isinstance(value, list)
                    else value
                )
            data["settings"] = entry.settings_cls(**converted)
        config = cls(**data)
        config.validate()
        return config


def resolve_overrides(
    entry: EffectEntry,
    preset: str | None,
    assignments: list[str],
    base: object | None = None,
) -> object | None:
    selected = effect_registry.resolve_settings(
        entry.name, preset=preset, settings=base
    )
    if not assignments:
        return selected
    cls = entry.settings_cls
    if cls is None or not is_dataclass(cls):
        raise ValueError(
            f"Effect '{entry.name}' does not accept dataclass setting overrides"
        )
    hints = get_type_hints(cls)
    changes = {}
    for assignment in assignments:
        key, separator, raw = assignment.partition("=")
        if not separator or key not in hints:
            raise ValueError(
                f"Expected FIELD=VALUE; available settings: {', '.join(hints)}"
            )
        if key in changes:
            raise ValueError(f"Setting '{key}' was supplied more than once")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        if get_origin(hints[key]) is tuple and isinstance(value, list):
            value = tuple(value)
        changes[key] = value
    # replace preserves all selected preset fields and invokes dataclass validation.
    if selected is None:
        return cls(**changes)
    assert is_dataclass(selected) and not isinstance(selected, type)
    return replace(selected, **changes)
