"""Classify GitHub changes without leaving required workflows pending."""

import json
import os
import re
import subprocess
from pathlib import Path


def scope(paths: list[str]) -> tuple[bool, bool]:
    """Return full-suite/docs requirements; unknown files conservatively run both."""
    full = docs = False
    for path in paths:
        if path.startswith("docs/") or path.endswith(".md"):
            docs = True
        elif path.startswith("tests/"):
            full = True
        else:
            full = docs = True
    return full, docs


def main() -> None:
    full = docs = True
    if os.getenv("CI_FULL") != "true":
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        pr = event.get("pull_request")
        before = pr["base"]["sha"] if pr else event.get("before", "")
        after = pr["head"]["sha"] if pr else event.get("after", "")
        # New branches, manual invocations and unknown events run everything.
        if all(
            re.fullmatch(r"[0-9a-f]{40}", ref) and ref != "0" * 40
            for ref in (before, after)
        ):
            comparison = f"{before}...{after}" if pr else f"{before}..{after}"
            result = subprocess.run(
                ["git", "diff", "--name-only", "-z", comparison, "--"],
                check=True,
                stdout=subprocess.PIPE,
            )
            paths = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
            full, docs = scope([path for path in paths if path])
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"full={str(full).lower()}\ndocs={str(docs).lower()}\n")


if __name__ == "__main__":
    main()
