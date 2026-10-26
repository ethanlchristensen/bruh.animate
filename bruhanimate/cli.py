"""Registry-driven discovery and playback; importing this module is inert."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import MISSING, fields, is_dataclass, replace
from typing import get_origin, get_type_hints

from .bruheffect.registry import EffectEntry, effect_registry
from .capture import record
from .config import EffectConfig
from .export import ExportStyle, export_animation
from .player import play


def _nonnegative(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be finite and non-negative")
    return number


def _rate(value: str) -> float:
    number = _nonnegative(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _count(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bruhanimate", description="Discover and play terminal animations."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List available effects and descriptions")
    browser = commands.add_parser(
        "browse", help="Browse live effects and presets with arrow keys"
    )
    browser.add_argument("--seed", type=_count, default=42)
    browser.add_argument(
        "--audio", action="store_true", help="Include previews that open audio capture"
    )
    browser.add_argument("--frames", type=_count)
    for command, description in (
        ("presets", "Show preset names and their settings"),
        ("info", "Show an effect's settings, defaults, ranges and presets"),
        ("play", "Play an effect; q, Escape or Ctrl+C quits"),
        ("record", "Record an asciicast v2 file headlessly using virtual time"),
        ("export", "Export GIF or MP4 headlessly (requires bruhanimate[export])"),
        ("save-preset", "Save resolved settings and playback options as JSON"),
    ):
        sub = commands.add_parser(command, help=description, description=description)
        sub.add_argument("effect", choices=effect_registry.names())
        if command == "play":
            sub.add_argument(
                "--on-resize",
                choices=("raise", "resize"),
                default="raise",
                help="Resize policy: raise an error (default) or retain state and reflow",
            )
        if command in ("record", "export", "save-preset"):
            sub.add_argument("output", help="Output file path")
            sub.add_argument("--width", type=_count, default=80)
            sub.add_argument("--height", type=_count, default=24)
            sub.add_argument(
                "--overwrite",
                action="store_true",
                help="Replace an existing output file",
            )
        if command == "export":
            sub.add_argument("--font", help="Local TrueType/OpenType font path")
            sub.add_argument("--font-size", type=_count, default=16)
            sub.add_argument("--cell-width", type=_count, default=10)
            sub.add_argument("--cell-height", type=_count, default=20)
        if command in ("play", "record", "export", "save-preset"):
            sub.add_argument(
                "--config", help="Saved JSON preset; explicit flags override its values"
            )
            sub.add_argument(
                "--seed",
                type=_count,
                help="Independent random seed; overrides the selected settings",
            )
            sub.add_argument(
                "--preset", help="Preset name; use 'presets EFFECT' to list"
            )
            sub.add_argument(
                "--fps",
                type=_rate,
                default=argparse.SUPPRESS,
                help="Presentation frames/second (default: 30)",
            )
            sub.add_argument(
                "--updates-per-second",
                type=_rate,
                help="Simulation ticks/second (default: one tick per frame)",
            )
            sub.add_argument(
                "--frames",
                type=_count,
                help="Maximum presentations; 0 starts no effect",
            )
            sub.add_argument(
                "--duration",
                type=_nonnegative,
                help="Seconds after startup (virtual time for record); 0 starts no effect",
            )
            sub.add_argument(
                "--set",
                action="append",
                default=[],
                metavar="FIELD=VALUE",
                help="Override a setting; values are JSON or text (repeatable). Use 'info EFFECT' for fields.",
            )
            # Distinguish omitted options from explicit flags when loading JSON.
            for action in sub._actions:
                if action.dest in (
                    "updates_per_second",
                    "frames",
                    "duration",
                    "width",
                    "height",
                ):
                    action.default = argparse.SUPPRESS
    return parser


def _print_presets(entry: EffectEntry) -> None:
    presets = effect_registry.presets(entry.name)
    if not presets:
        print("No named presets; use the effect defaults.")
    for name, settings in presets.items():
        print(f"{name}: {settings!r}")


def _print_info(entry: EffectEntry) -> None:
    print(f"{entry.name}: {entry.description}")
    cls = entry.settings_cls
    if cls is None:
        print("Settings: none")
    elif is_dataclass(cls):
        print(f"Settings: {cls.__name__}")
        print((cls.__doc__ or "").strip())
        hints = get_type_hints(cls)
        for item in fields(cls):
            default = item.default
            if item.default_factory is not MISSING:
                default = item.default_factory()
            display = "required" if default is MISSING else repr(default)
            annotation = hints.get(item.name, item.type)
            typename = getattr(annotation, "__name__", str(annotation))
            # Keep Literal options and container element types visible.
            if get_origin(annotation) is not None:
                typename = str(annotation).removeprefix("typing.")
            constraints = []
            if item.metadata.get("min") is not None:
                constraints.append(f"min={item.metadata['min']}")
            if item.metadata.get("max") is not None:
                constraints.append(f"max={item.metadata['max']}")
            if item.metadata.get("help"):
                constraints.append(item.metadata["help"])
            suffix = f" ({'; '.join(constraints)})" if constraints else ""
            print(f"  {item.name}: {typename} = {display}{suffix}")
    else:
        print(f"Settings: {cls.__name__} (configure in Python)")
    print("Presets:")
    _print_presets(entry)


def _settings(
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Discovery never opens a Screen or constructs an effect."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "browse":
        from .browser import EffectBrowser

        selected: list[EffectBrowser] = []

        def build(buffer):
            preview = EffectBrowser(
                size=(buffer.width(), buffer.height()),
                seed=args.seed,
                include_audio=args.audio,
            )
            selected.append(preview)
            return preview

        play(
            effect_factory=build,
            event_handler=lambda event: selected[0].handle_event(event),
            frames=args.frames,
            fps=30,
            updates_per_second=30,
            on_resize="resize",
        )
        if selected:
            print(selected[0].command)
        return 0
    if args.command == "list":
        for name in effect_registry.names():
            print(f"{name}: {effect_registry.get(name).description}")
        return 0
    entry = effect_registry.get(args.effect)
    if args.command == "presets":
        _print_presets(entry)
    elif args.command == "info":
        _print_info(entry)
    else:
        try:
            config = (
                EffectConfig.load(args.config)
                if args.config
                else EffectConfig(entry.name)
            )
            if config.effect != entry.name:
                raise ValueError(f"Config is for {config.effect!r}, not {entry.name!r}")
            for option in (
                "fps",
                "updates_per_second",
                "frames",
                "duration",
                "width",
                "height",
            ):
                if not hasattr(args, option):
                    setattr(args, option, getattr(config, option))
            # An explicit named preset replaces the saved settings selection.
            settings = _settings(
                entry,
                args.preset,
                args.set,
                config.settings if args.preset is None else None,
            )
            settings = effect_registry.resolve_settings(
                entry.name, settings=settings, preset=args.preset, seed=args.seed
            )
        except (OSError, KeyError, TypeError, ValueError) as error:
            parser.error(str(error))
        if args.command in ("save-preset", "export"):
            try:
                if args.command == "save-preset":
                    EffectConfig(
                        entry.name,
                        settings,
                        args.fps,
                        args.updates_per_second,
                        args.frames,
                        args.duration,
                        args.width,
                        args.height,
                    ).save(args.output, overwrite=args.overwrite)
                else:
                    export_animation(
                        args.output,
                        entry.name,
                        settings=settings,
                        preset=args.preset,
                        width=args.width,
                        height=args.height,
                        fps=args.fps,
                        updates_per_second=args.updates_per_second,
                        frames=args.frames,
                        duration=args.duration,
                        overwrite=args.overwrite,
                        style=ExportStyle(
                            font=args.font,
                            font_size=args.font_size,
                            cell_size=(args.cell_width, args.cell_height),
                        ),
                    )
            except (
                OSError,
                KeyError,
                TypeError,
                ValueError,
                RuntimeError,
                ImportError,
            ) as error:
                parser.error(str(error))
            return 0
        if args.command == "record":
            try:
                record(
                    entry.name,
                    args.output,
                    settings=settings,
                    preset=args.preset,
                    width=args.width,
                    height=args.height,
                    fps=args.fps,
                    updates_per_second=args.updates_per_second,
                    frames=args.frames,
                    duration=args.duration,
                    overwrite=args.overwrite,
                )
            except (OSError, KeyError, TypeError, ValueError) as error:
                parser.error(str(error))
            return 0
        play(
            entry.name,
            preset=args.preset,
            settings=settings,
            fps=args.fps,
            updates_per_second=args.updates_per_second,
            frames=args.frames,
            duration=args.duration,
            on_resize=args.on_resize,
        )
    return 0
