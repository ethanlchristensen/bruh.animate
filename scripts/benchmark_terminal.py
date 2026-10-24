"""Benchmark actual Screen writes and flushes in your interactive terminal.

Run from the checkout with uv run --locked python scripts/benchmark_terminal.py
--effect plasma --output native-plasma.json. No extra dependencies are required.
The benchmark runs unpaced; it does not measure terminal/GPU display latency.
"""

import argparse
import json
import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bruhanimate import Screen, effect_registry
from bruhanimate.demos.windows_demo import build_scene
from scripts.benchmark_rendering import measure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--effect",
        choices=("snow", "fire", "plasma", "matrix", "four_windows"),
        default="plasma",
    )
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument(
        "--update-every",
        type=int,
        default=1,
        help="Update once every N presentations; simulated presentation interval is 1/60 second",
    )
    parser.add_argument(
        "--output", type=Path, help="JSON destination; parent must exist"
    )
    args = parser.parse_args(argv)
    if args.samples < 1 or args.warmup < 0 or args.update_every < 1:
        parser.error(
            "samples/update-every must be positive; warmup must be non-negative"
        )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error(
            "requires an interactive terminal on stdin and stdout; use --output instead of redirecting stdout"
        )
    factory = (
        (lambda b: build_scene(b, audio_mode=None))
        if args.effect == "four_windows"
        else lambda b: effect_registry.create(args.effect, b, " ", seed=42)
    )
    screen = Screen.open()
    try:
        result = measure(
            args.effect,
            factory,
            (screen.width, screen.height),
            warmup=args.warmup,
            samples=args.samples,
            update_every=args.update_every,
            screen=screen,
        )
    finally:
        screen.close()
    report = {
        "backend": "native Screen writes/flushes; excludes terminal/GPU display latency",
        "python": sys.version,
        "platform": platform.platform(),
        "terminal": os.environ.get("TERM_PROGRAM")
        or os.environ.get("TERM")
        or "unknown",
        "windows_terminal": bool(os.environ.get("WT_SESSION")),
        "samples": args.samples,
        "warmup": args.warmup,
        "paced": False,
        "results": [result],
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
