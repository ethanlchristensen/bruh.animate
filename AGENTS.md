# Contributing to bruhanimate

## Scope and architecture

This repository contains the 1.x terminal-animation library, demos, Sphinx docs,
and release tooling. Read the relevant modules and tests before editing. If the
Codegraph index is available, use it for symbol/caller exploration. Keep changes
focused and preserve unrelated working-tree changes.

- `player.py`: the only playback loop, input polling, clocks and presentation.
- `scene.py`: ordered composition, transparency and child lifecycle ownership.
- `playback.py`: lazy solver snapshots, solver controls and source cleanup.
- `history.py`, `background.py`: opt-in bounded history and cooperative solver workers.
- `config.py`, `browser.py`: validated saved settings and one owned live preview.
- `tween.py`, `themes.py`, `cache.py`: interpolation, shared palettes and explicit drawing caches.
- `_clock.py`, `_validation.py`: shared simulation clocks and time validation.
- `grid.py`: board coordinates, camera, clipping and single-cell styling.
- `bruheffect/`: built-in simulations, settings and the discovery registry.
- `bruhutil/`: Buffer invariants and platform Screen implementations.
- `scripts/`, `publish.py`, `.github/`: checks, release preparation and CI.

Animations implement `start()`, `update(dt)`, `draw(buffer)` and `close()`.
Construction and imports must not open terminals, devices, threads, subprocesses,
or invoke a shell. Draw must not advance simulation, consume input states or
mutate a previously presented frame. BaseEffect supplies persistent-raster draw;
its update method is abstract. Built-ins use simulation ticks, while dt is seconds.

Player owns supplied content by default and borrows its Screen. Scene owns its
children and closes them in reverse startup order, including partial failures.
Close must be idempotent and safe before/after failed startup. Do not share an
animation instance between owners. Playback owns its acquired iterator, retains
one snapshot, and never eagerly materializes a solver trace.

None cells are transparent; plain spaces paint unless Layer explicitly opts into
space transparency. Grid glyphs occupy one cell with optional ANSI SGR styling.
Wide/combining glyphs and cursor escapes are unsupported. Preserve rectangular
Buffer dimensions, clipped drawing and changed-cell presentation.

The 1.0 release intentionally removes the old renderer hierarchy and legacy
render_frame adapters. Do not restore compatibility wrappers without a new API
decision. Keep puzzle-specific branching and visual rules in application code.
The separate AdventOfCodeSolutions repository is not part of the package; edit
it only within the user's requested scope and retain originals when comparing.

## Development and checks

Use Python 3.13 and uv 0.13.4. Commit `uv.lock`; it pins repository/CI
environments, not consumers' installations. Dependency updates must refresh it.
The uv version is pinned in `[tool.uv].required-version`; keep CI and installation
examples aligned with it. Use standard `[dependency-groups]` for dev/docs tools.
`poetry-core` is only the PEP 517 build backend; the Poetry CLI is not required.

```sh
uv sync --locked --group docs
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
uv run --locked python scripts/check_examples.py
uv run --locked --group docs python scripts/build_docs.py
uv run --locked python scripts/release_check.py
```

Run relevant tests during implementation, then the complete suite for release or
cross-cutting changes. Use fake clocks and recording Screens for deterministic
playback tests. Stub physical audio and avoid opening real terminals in automated
tests. Keep resource-ownership/process tests meaningful. Label native terminal,
hardware-audio and platform checks accurately; mocked tests do not establish
hardware support. CI runs Python 3.13 on Linux, Windows and macOS.

For a complete local release check, run `uv run --locked python publish.py --check`.
It also builds fresh archives and checks package metadata with Twine. Source and
installed-distribution tests are different: CI installs both the wheel and sdist
and runs `python -I scripts/check_installed.py` to avoid checkout imports.
Run installed-artifact checks directly with the environment's Python; `uv run`
with synchronization can restore an editable project and hide packaging errors.

## Documentation and API changes

Keep AI-session plans and progress notes local. `docs/DESIGN_PROPOSAL.md` and
`docs/ROADMAP.md` are ignored and must not be force-added. README.md, AGENTS.md,
and user-facing documentation remain tracked. Do not link public documentation
to local session notes.

Update README examples, public docstrings and the relevant guide together.
`scripts/check_examples.py` executes current Python examples from README,
`docs/PLAYER.md`, `docs/SOLVER_PLAYBACK.md`, and the top-level documentation-site
RST pages. Keep those examples standalone; historical Markdown migration snippets
are excluded deliberately. Shell/release commands are never executed by this check.
Sphinx builds treat warnings as errors and disable remote
intersphinx inventory requests by default. Use `--online-inventories` explicitly
when checking those external references.

Describe ownership, units, completion and input-routing behavior when changing
these contracts. Document breaking changes in `docs/MIGRATING_1.0.md` or the next
version's migration notes. Keep `docs/ROADMAP.md` honest about completed work,
limitations and checks that were actually run. Do not copy private puzzle inputs
or credentials into demos, docs, tests or distribution archives.

## Release workflow

`pyproject.toml` and `bruhanimate.__version__` must match. The helper previews by
default; write/commit/push/PR operations require explicit flags. Write mode refreshes
`uv.lock` after bumping the package version and includes it in an explicit commit.
Check mode rejects stale lockfiles. It never creates a release tag. Read
`docs/RELEASING.md` before changing these semantics.

Merging into main runs CI/docs; pushing a matching `vMAJOR.MINOR.PATCH` tag starts
publishing. The tag must point to a main-branch commit. Release jobs validate the
exact commit, run CI/docs, and publish the verified artifact in a separate job.
Build/test jobs have read-only permissions. Pages deploys only from main.
Keep third-party Actions pinned to full commit SHAs and update their version
comments. Dependabot version-update schedules are removed to prevent bot PRs and
extra CI runs; do not re-enable them without the user's request.
Refresh pins manually when updating Actions. Do not print tokens or interpolate
untrusted workflow input directly into shell programs.

Do not commit, push, create PRs/tags, publish packages or deploy from an agent
session unless the user has authorized that action. Workflows/publish helpers
being present do not themselves grant authorization. Never rewrite published
versions/tags to repair a release; follow the retry procedure or prepare a new
version. Keep `.env`, local indexes and build output out of version control.
