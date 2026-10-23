"""Execute current Markdown Python examples using the real player headlessly."""

import contextlib
import io
import re
from pathlib import Path
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
        for filename in ("README.md", "docs/PLAYER.md", "docs/SOLVER_PLAYBACK.md"):
            for block in re.findall(
                r"```python\n(.*?)```",
                (root / filename).read_text(encoding="utf-8"),
                re.S,
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(block, f"{filename}:example-{count + 1}", "exec"), {})
                count += 1
    print(f"Verified {count} current-API documentation examples")


if __name__ == "__main__":
    main()
