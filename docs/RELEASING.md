# Releasing bruhanimate

Releases are **tag-driven**. A normal push or merge to main runs CI and builds
documentation; it no longer publishes a package. Pushing `vMAJOR.MINOR.PATCH`
starts the release workflow. This is a deliberate change from the old pipeline.

## One-time repository configuration

Use GitHub Actions as the GitHub Pages source. The `github-pages` environment
receives deployments only from main; PRs build/upload docs for review without
deployment permissions. Protect main with the CI and Documentation checks.

The package upload job uses the `pypi` environment. Add any desired environment
reviewers and allow release tags. It supports these authentication modes:

- **Trusted Publishing:** configure the existing PyPI project's publisher with
  owner `FNBBDevs`, repository `bruhanimate`, workflow `release.yml`, and
  environment `pypi`.
  Remove `PYPI_TOKEN` from repository/environment secrets once configured. The
  empty password selects OIDC, and the action produces attestations.
- **Existing token:** keeping a project-scoped `PYPI_TOKEN` continues to work.
  It takes precedence over OIDC, and attestations are disabled for token uploads.

Do not put tokens into scripts, workflow inputs, command arguments or files.
Trusted Publishing setup lives in PyPI/GitHub settings and cannot be established
by committing a workflow alone. See the official [PyPI setup guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [publishing action](https://github.com/pypa/gh-action-pypi-publish).

## Validate the current release

Use Python 3.13 and the uv version pinned in pyproject.toml:

```sh
python -m pip install uv==0.13.4
uv sync --locked --group docs
uv run --locked python publish.py --check
```

For an existing standalone uv installation, use `uv self update 0.13.4` instead
of installing through pip. Confirm `uv --version` reports the pinned version.

This checks matching source versions, Ruff, tests, current documentation examples,
strict Sphinx HTML, fresh wheel/sdist contents and Twine metadata. It does not
change versions, commit, push, create a PR or publish. Build products go into an
ignored temporary subdirectory of build, removed when checking finishes.

`uv.lock` is committed so CI uses a consistent dependency resolution. After
editing dependencies, run `uv lock` and commit its changes. Distribution
dependency ranges still govern library consumers; their environments do not use
the repository lockfile.

uv manages environments, dependency groups and builds. `poetry-core` remains the
PEP 517 build backend; the Poetry CLI is not required. `uv build --no-sources`
checks that artifacts build from standard package metadata. CI installs uv using
the version pinned in `[tool.uv].required-version`; upgrade that pin and the
installation examples together. To migrate an existing checkout, install uv and
run the sync command above; it can reuse `.venv` without Poetry activation.

The PyPA upload action remains responsible for publishing: it generates Trusted
Publishing attestations, while `uv publish` currently only uploads attestations
generated elsewhere. See [uv's publishing guide](https://docs.astral.sh/uv/guides/publish/).
Do not run `uv publish` locally as an additional release step.

The local dist folder may contain historical archives. Keep them for reference;
the release workflow publishes only its fresh build/release artifact. Do not
upload every file in an old dist folder. The archive check rejects stale or
unexpected files instead of silently publishing them. Coverage and test reports
are retained as workflow artifacts; no external Codecov token is required.

## Prepare a future version

The current 1.0.0 source version is already prepared. Use --check for this release;
do not accidentally bump it to 1.0.1 before publishing 1.0.0.

```sh
# Preview a future version without writing anything:
uv run --locked python publish.py
uv run --locked python publish.py 1.1.0

# Edit both version files, then run checks; no Git operations:
uv run --locked python publish.py 1.1.0 --write
```

The helper accepts stable MAJOR.MINOR.PATCH versions, rejects leading zeros,
downgrades, equal versions and mismatched metadata. It validates both version
assignments before writing; a failed second write restores the first. Write mode
then refreshes `uv.lock`, which records the root package version. Existing
compatible dependency pins are retained. If locking or checks fail after a
successful bump, the local edits remain reviewable and no commit or push happens;
fix the failure, run `uv lock`, and retry with --check.

Optional Git operations are separate explicit flags:

```sh
# Run on a clean feature branch, after committing other changes:
uv run --locked python publish.py 1.1.0 --write --commit --push --pr
```

--commit requires --write; --push requires --commit; --pr requires --push and an
authenticated GitHub CLI. The helper rejects main/master, detached HEAD and a
dirty checkout before changing versions in this mode. It stages the two version
files and `uv.lock`. It runs from the repository root even when invoked elsewhere and
uses a temporary body file for PR text. Merging the PR does not publish anything.
The helper never creates or pushes a release tag.

## Publish a reviewed main commit

After review, merge and wait for main's checks. From a clean main checkout:

```sh
git switch main
git pull --ff-only
uv run --locked python publish.py --check
git tag -a v1.0.0 -m "bruhanimate 1.0.0"
git push origin v1.0.0
```

Replace the version for future releases. `pyproject.toml`'s project.version,
`bruhanimate.__version__` and the v-prefixed tag must match exactly. The workflow
requires the tag commit to be an ancestor of origin/main, resolves its exact SHA,
and passes that SHA to the checks. Stable releases only are supported by this
helper/workflow; pre-release suffixes require an explicit future design change.

The release workflow performs:

1. Version/tag/main ancestry validation.
2. The same reusable CI as PRs: lint, metadata/lock checks, tests on Linux/Windows/
   macOS with Python 3.13, package construction and archive checks.
3. Installation and isolated import/API smoke tests for both wheel and sdist,
   preventing an editable checkout from hiding missing package files.
4. Executable documentation examples and Sphinx with warnings treated as errors.
5. Upload of the **verified build artifact** from a separate job with PyPI/OIDC
   permissions; this job does not check out or execute project code.
6. GitHub release creation: upload assets to a draft, then publish it. Generated
   release notes replace the old shell-based commit-message parser. Existing
   published release assets are left intact.

Actions are pinned to commit SHAs and maintained through Dependabot. The build
jobs have read-only repository permissions. Only package upload, GitHub release,
and Pages deployment receive their specific additional permissions.

## Retry a partial failure

Prefer GitHub's **Re-run failed jobs** on the original run. Its retained artifacts
preserve the exact files that passed checks. Package upload skips files already
present, so a partially successful upload can finish. A failed GitHub-release job
can finish its draft without repeating a successful PyPI job.

For a new run, dispatch the Release workflow with the existing tag:

```sh
gh workflow run release.yml --ref main -f tag=v1.0.0
```

This validates and rebuilds the tagged commit. Build outputs may have different
archive timestamps, so existing PyPI files remain authoritative when skipped.
An existing published GitHub release is not overwritten. Do not move or recreate
published tags or reuse a version for code changes; release a new version instead.
If artifacts have expired, inspect the existing PyPI/GitHub release before retrying.

## Documentation commands

```sh
uv run --locked python scripts/check_examples.py
uv run --locked --group docs python scripts/build_docs.py
# Optional external inventory validation:
uv run --locked --group docs python scripts/build_docs.py --online-inventories
```

Default documentation builds do not fetch external intersphinx inventories, so
network outages do not make otherwise valid docs fail. Sphinx warnings still fail
the build. Imports are inert, so the old fake pyaudio modules are unnecessary.

Workflow syntax can be checked with [actionlint](https://github.com/rhysd/actionlint).
Repository tests also guard tag-only publishing, privileged job separation,
PR deployment conditions, version edits and archive validation. Local checks do
not prove that remote credentials/environment settings are correct; the first
tagged run verifies those external integrations.
