"""Preview or prepare a release; publication happens only after a release-tag push.

Default: preview the next patch (or supplied version), without writes or Git calls.
--check validates the current release without changing its version.
--write updates versions and runs local checks; --commit, --push and --pr each
require their preceding explicit flag. Never creates or pushes a release tag.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.release_check import ROOT, check_dist, parse_version, source_version


def bump_version(
    pyproject: Path, module: Path, new_version: tuple[int, int, int] | None = None
):
    """Validate both files before writing; roll back the first if the second fails.

    This operation edits only these two files, never Git. It requires matching
    canonical stable versions and a strictly increasing target version.
    """
    root = pyproject.parent
    current = source_version(root)
    old = parse_version(current)
    new = new_version if new_version is not None else (old[0], old[1], old[2] + 1)
    target = ".".join(map(str, new))
    parse_version(target)
    if new <= old:
        raise ValueError("The new version must be greater than the current version")
    patterns = (
        r'(?ms)(^\[project\][^\n]*\n(?:(?!^\[).)*?^version\s*=\s*")'
        + re.escape(current)
        + r'(")',
        r'(^__version__\s*=\s*")' + re.escape(current) + r'(")',
    )
    originals, replacements = [], []
    for path, pattern in zip((pyproject, module), patterns):
        text = path.read_text(encoding="utf-8")
        updated, count = re.subn(
            pattern,
            lambda match: match[1] + target + match[2],
            text,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise ValueError(f"Expected exactly one version assignment in {path.name}")
        originals.append(text)
        replacements.append(updated)
    pyproject.write_text(replacements[0], encoding="utf-8")
    try:
        module.write_text(replacements[1], encoding="utf-8")
    except BaseException:
        pyproject.write_text(originals[0], encoding="utf-8")
        raise
    return old, new


def command(args: list[str], *, root: Path = ROOT, capture: bool = False) -> str:
    """Run an argument list from the repository root, propagating command failure."""
    result = subprocess.run(
        args,
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def validate(root: Path = ROOT) -> None:
    """Sync locked dev/docs/export tools, then check source and fresh archives.

    A stale lockfile fails instead of silently changing dependency resolution.
    Builds use standard package metadata without local uv source overrides.
    """
    uv = uv_executable()
    source_version(root)
    command([uv, "sync", "--locked", "--group", "docs", "--extra", "export"], root=root)
    for args in (
        ["ruff", "check", "."],
        ["mypy"],
        ["pytest"],
        ["python", "scripts/check_examples.py"],
        ["python", "scripts/build_docs.py"],
    ):
        command([uv, "run", "--no-sync", *args], root=root)
    build = root / "build"
    build.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="release-", dir=build) as temporary:
        command(
            [
                uv,
                "build",
                "--no-sources",
                "--no-create-gitignore",
                "--out-dir",
                temporary,
            ],
            root=root,
        )
        check_dist(Path(temporary), source_version(root))
        command(
            [
                uv,
                "run",
                "--no-sync",
                "python",
                "-m",
                "twine",
                "check",
                "--strict",
                *map(str, sorted(Path(temporary).iterdir())),
            ],
            root=root,
        )


def uv_executable() -> str:
    """Find uv without invoking an installation or modifying the user's tools."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install the uv version in pyproject.toml first")
    return uv


def preflight_git(root: Path, *, create_pr: bool) -> str:
    """Reject detached/main/dirty checkouts before any version or Git mutation."""
    branch = command(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"], root=root, capture=True
    )
    if branch in ("main", "master"):
        raise ValueError("Prepare the release on a feature branch, not main/master")
    if command(["git", "status", "--porcelain"], root=root, capture=True):
        raise ValueError(
            "Commit or stash existing work before --commit; the checkout must be clean"
        )
    if create_pr:
        if shutil.which("gh") is None:
            raise RuntimeError(
                "--pr requires an installed and authenticated GitHub CLI"
            )
        command(["gh", "auth", "status"], root=root)
    return branch


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "version", nargs="?", help="Target stable version; defaults to the next patch"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the current release; no version/Git changes",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update both version files and run all checks",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit the version files and refreshed uv.lock (requires --write)",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the preparation branch (requires --commit)",
    )
    parser.add_argument(
        "--pr", action="store_true", help="Open a PR into main (requires --push)"
    )
    args = parser.parse_args(argv)
    for selected, required in (("commit", "write"), ("push", "commit"), ("pr", "push")):
        if getattr(args, selected) and not getattr(args, required):
            parser.error(f"--{selected} requires --{required}")
    if args.check and (args.version or args.write):
        parser.error(
            "--check validates the current version and cannot be combined with a target or --write"
        )
    current = source_version(root)
    if args.check:
        validate(root)
        print(
            f"Release v{current} passed local checks. No version or Git changes made."
        )
        return 0
    old = parse_version(current)
    target = (
        parse_version(args.version) if args.version else (old[0], old[1], old[2] + 1)
    )
    if target <= old:
        raise ValueError(
            "The target version must be greater than the current version; use --check for this release"
        )
    version = ".".join(map(str, target))
    print(f"Release plan: {current} -> {version}")
    if not args.write:
        print(
            "Preview only. Add --write to update versions and run checks; Git operations require explicit flags."
        )
        return 0
    branch = preflight_git(root, create_pr=args.pr) if args.commit else None
    uv = uv_executable()
    bump_version(root / "pyproject.toml", root / "bruhanimate/__init__.py", target)
    # uv.lock includes the root package version. Refresh it only in write mode;
    # uv preserves existing compatible pins unless an upgrade is requested.
    command([uv, "lock"], root=root)
    validate(root)
    if args.commit:
        command(
            [
                "git",
                "add",
                "--",
                "pyproject.toml",
                "bruhanimate/__init__.py",
                "uv.lock",
            ],
            root=root,
        )
        command(["git", "commit", "-m", f"chore: prepare v{version}"], root=root)
    if args.push:
        command(["git", "push", "--set-upstream", "origin", branch], root=root)
    if args.pr:
        with TemporaryDirectory(prefix="release-pr-", dir=root / "build") as temporary:
            body = Path(temporary) / "body.md"
            body.write_text(
                f"Prepare bruhanimate {version}.\n\nLocal lint, tests, docs and package checks passed.\nMerging does not publish. Push v{version} from the reviewed main commit to release.\n",
                encoding="utf-8",
            )
            url = command(
                [
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    "main",
                    "--head",
                    branch,
                    "--title",
                    f"Release v{version}",
                    "--body-file",
                    str(body),
                ],
                root=root,
                capture=True,
            )
            print(url)
    print(
        f"Prepared v{version}. After review/merge, tag the main commit to publish. No release tag was created."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
