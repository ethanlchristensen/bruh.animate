"""Repeatable CPU rendering benchmark; never opens a terminal or sleeps.

Run with ``uv run --locked python scripts/benchmark_rendering.py --output result.json``.
The in-memory ANSI formatter excludes native terminal I/O and input/pacing costs.
Use identical seeds, dimensions, warmup, samples and Python environments to compare.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bruhanimate import (
    Animation,
    Buffer,
    CachedAnimation,
    CallbackEffect,
    FramePresenter,
    Panel,
    Scene,
    effect_registry,
)
from bruhanimate.demos.windows_demo import build_scene


class FormattingScreen:
    """Mirror buffered ANSI output to memory, without platform initialization."""

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self._x = self._y = -1
        self._parts: list[str] = []
        self.output = ""

    def begin_frame(self) -> None:
        self._parts = []

    def print_at(self, text: str, x: int, y: int, width: int) -> None:
        cursor = f"\x1b[{y + 1};{x + 1}H" if (x, y) != (self._x, self._y) else ""
        self._parts.append(cursor + str(text))
        self._x, self._y = x + width, y

    def flush_frame(self) -> None:
        self.output = "".join(self._parts)
        self._parts = []


def summary(values: list[int]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(values) / 1e6, 3),
        "p95_ms": round(sorted(values)[int(0.95 * (len(values) - 1))] / 1e6, 3),
    }


def measure(
    name: str,
    factory: Callable[[Buffer], Animation],
    size: tuple[int, int],
    *,
    warmup: int,
    samples: int,
    update_every: int = 1,
    screen=None,
) -> dict:
    width, height = size
    animation = factory(Buffer(height, width))
    screen = FormattingScreen(width, height) if screen is None else screen
    presenter = FramePresenter(screen)
    frame = Buffer(height, width)
    timings: dict[str, list[int]] = {
        key: [] for key in ("update", "draw", "present", "total")
    }
    byte_counts = []
    try:
        animation.start()
        for index in range(warmup + samples):
            if not isinstance(screen, FormattingScreen) and screen.has_resized():
                raise RuntimeError(
                    "Terminal resized during benchmark; rerun at a stable size"
                )
            start = perf_counter_ns()
            if index % update_every == 0:
                animation.update(update_every / 60)
            updated = perf_counter_ns()
            frame.clear_buffer()
            animation.draw(frame)
            drawn = perf_counter_ns()
            frame = presenter.present(frame)
            end = perf_counter_ns()
            if index >= warmup:
                for key, value in zip(
                    timings,
                    (updated - start, drawn - updated, end - drawn, end - start),
                ):
                    timings[key].append(value)
                if isinstance(screen, FormattingScreen):
                    byte_counts.append(len(screen.output.encode("utf-8")))
    finally:
        animation.close()
    return {
        "name": name,
        "size": size,
        "update_every": update_every,
        **{key: summary(values) for key, values in timings.items()},
        "mean_output_bytes": round(statistics.mean(byte_counts))
        if byte_counts
        else None,
    }


def panels(count: int, buffer: Buffer) -> Scene:
    return Scene(
        *(
            Panel(
                CallbackEffect(lambda b: b.clear_buffer(val="x")),
                size=(10, 4),
                position=((i * 12) % buffer.width(), (i // 8) * 6),
            )
            for i in range(count)
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=80)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument(
        "--output", type=Path, help="Optional JSON destination; parent must exist"
    )
    args = parser.parse_args()
    if args.samples < 1 or args.warmup < 0:
        parser.error("samples must be positive and warmup must be non-negative")
    results = []

    def record(name, factory, size, update_every=1):
        row = measure(
            name,
            factory,
            size,
            warmup=args.warmup,
            samples=args.samples,
            update_every=update_every,
        )
        results.append(row)
        print(json.dumps(row), flush=True)

    for size in ((80, 24), (160, 48), (240, 80)):
        for name in ("snow", "fire", "plasma", "matrix"):
            record(
                name,
                lambda b, name=name: effect_registry.create(name, b, " ", seed=42),
                size,
            )
        record("four_windows", lambda b: build_scene(b, audio_mode=None), size)
    for count in (1, 4, 16):
        for size in ((80, 24), (240, 80)):
            record(
                f"{count}_small_panels", lambda b, count=count: panels(count, b), size
            )
    for size in ((80, 24), (240, 80)):
        record("16_cached_panels", lambda b: CachedAnimation(panels(16, b)), size)
    record(
        "fire_15ups_60fps",
        lambda b: effect_registry.create("fire", b, " ", seed=42),
        (160, 48),
        update_every=4,
    )
    if args.output:
        args.output.write_text(
            json.dumps(
                {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "processor": platform.processor(),
                    "samples": args.samples,
                    "warmup": args.warmup,
                    "backend": "in-memory ANSI formatter; excludes native I/O",
                    "results": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
