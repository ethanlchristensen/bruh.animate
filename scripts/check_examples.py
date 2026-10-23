"""Execute current Markdown and site Python examples through the real player.

Only Python examples run; shell/release instructions are never executed.
Historical before/after migration snippets are excluded deliberately.
"""

import contextlib
import io
import re
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch


class HeadlessScreen:
    """Minimal Screen boundary; examples still exercise real effect composition."""

    height, width = 12, 40

    def close(self):
        pass

    def has_resized(self):
        return False

    def get_event(self):
        return None

    def begin_frame(self):
        pass

    def flush_frame(self):
        pass

    def print_at(self, text, x, y, width):
        pass


def python_examples(path: Path):
    """Yield standalone Python fences or top-level RST code-block directives."""
    pattern = (
        r"```python\n(.*?)```"
        if path.suffix == ".md"
        else r"(?m)^\.\. code-block:: python[ \t]*\n((?:[ \t]*\n|[ \t]+[^\n]*\n)*)"
    )
    flags = re.S if path.suffix == ".md" else 0
    for block in re.findall(pattern, path.read_text(encoding="utf-8"), flags):
        yield dedent(block)


def main() -> None:
    from bruhanimate import Player, Screen

    original_run = Player.run

    def run(player):
        now = 0.0

        def sleep(seconds):
            nonlocal now
            now += seconds

        player.clock, player.sleep, player.frames = lambda: now, sleep, 2
        return original_run(player)

    root = Path(__file__).resolve().parents[1]
    count = 0
    with (
        patch.object(Player, "run", run),
        patch.object(Screen, "open", classmethod(lambda cls: HeadlessScreen())),
    ):
        pages = [
            root / "README.md",
            root / "docs/PLAYER.md",
            root / "docs/SOLVER_PLAYBACK.md",
            *sorted((root / "docs/source").glob("*.rst")),
        ]
        for page in pages:
            # The migration page contains its own complete v1 example. Old API
            # fragments in docs/MIGRATING_1.0.md remain outside this selection.
            for number, block in enumerate(python_examples(page), 1):
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(
                        compile(block, f"{page.relative_to(root)}:example-{number}", "exec"),
                        {},
                    )
                count += 1
    print(f"Verified {count} current-API documentation examples")


if __name__ == "__main__":
    main()
