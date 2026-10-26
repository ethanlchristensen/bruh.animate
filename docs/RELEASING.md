# Release process

**Develop on `dev`, merge into `main`, wait for green checks, then push a version
tag when you are ready to publish.** Merging alone does not upload a package.

The local ``publish.py --check`` gate installs the optional export extra to run
real PNG/GIF/MP4 regressions. CI also runs those tests on all three supported
platforms and native PTY resize checks on Linux/macOS. Hardware audio and visual
terminal checks remain explicit; see [native checks](source/platform_checks.rst).

This is the maintainer checklist for bruhanimate. All commands run from the
repository root; examples use 1.0.0 unless another target is specified.

## What triggers what?

| Event | CI and package checks | Docs | PyPI / GitHub release |
| --- | --- | --- | --- |
| Open or update a PR into `main` | Run | Build for review | No |
| Merge or push to `main` | Run | Build and deploy Pages | No |
| Push `vMAJOR.MINOR.PATCH` | Run again for the tag's exact commit | Build as a release gate | Yes, after every gate passes |
| Manually run Release with an existing tag | Same release checks | Build as a release gate | Retry publication |

Documentation-only commits skip the CI matrix; test-only commits skip docs.
Lightweight change-classification jobs still report results, so required checks
do not stay pending. Source, dependency, workflow and unknown changes run both.
Release refs and manual validation always run all gates.

A standalone push to `dev` has no branch-push workflow; an open PR targeting main
receives checks when its branch changes. Docs can be released independently of a
package by merging documentation changes to main.

## 1. Configure publishing once

The canonical repository is
[`ethanlchristensen/bruh.animate`](https://github.com/ethanlchristensen/bruh.animate).
Older `FNBBDevs/bruhanimate` links redirect; use the current identity for publishing.

In GitHub settings:

- Protect main with the CI and Documentation checks.
- Set **Pages → Build and deployment → Source → GitHub Actions**. The site is
  [ethanlchristensen.github.io/bruh.animate](https://ethanlchristensen.github.io/bruh.animate/).
- Configure the `pypi` environment to allow release tags. Add reviewers if desired.
  The separate `github-pages` environment handles documentation deployment.

Package uploads use Trusted Publishing (OIDC) with attestations. In PyPI →
bruhanimate → Manage → Publishing, add the GitHub identity below before the next
release. Each PyPI project needs its own publisher; configuring bruhcolor does
not configure bruhanimate.

Trusted Publisher fields must match exactly:

| Field | Value |
| --- | --- |
| PyPI project | `bruhanimate` |
| GitHub owner | `ethanlchristensen` |
| GitHub repository | `bruh.animate` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The workflow does not read `PYPI_TOKEN`; an existing secret cannot override OIDC.
After confirming a successful Trusted Publishing release, remove the unused
repository/environment secret and revoke the old PyPI token if no other workflow
uses it. These settings live in PyPI/GitHub and are not created by
committing the workflow. See the [PyPI setup instructions](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [publishing action](https://github.com/pypa/gh-action-pypi-publish).

## 2. Prepare the version on dev

Start with a clean checkout containing the work you intend to release:

```sh
git switch dev
git pull --ff-only
uv sync --locked --group docs
```

Use Python 3.13 and the uv version pinned in `[tool.uv].required-version`
(currently 0.13.4). Install with `python -m pip install uv==0.13.4`, or update a
standalone installation with `uv self update 0.13.4`.

If the intended version is **already prepared**, validate it without bumping:

```sh
uv lock --check
uv run --locked python publish.py --check
```

For example, if the source already says 1.0.0 and that version has not been
published, use --check to prepare its first release. Do not bump to 1.0.1 just
because another check is needed.

For a **new version**, preview the target, then explicitly write it:

```sh
# Preview only; no source writes, commits, pushes, or tags:
uv run --locked python publish.py 1.1.0

# Update both version files, refresh uv.lock, and run all local checks:
uv run --locked python publish.py 1.1.0 --write
```

With no target, the helper previews the next patch version. It accepts canonical
stable MAJOR.MINOR.PATCH versions, requires an increase in write mode, and rejects
prerelease suffixes and leading zeros. Update migration notes and public examples
when the API changes.

### Version and lockfile agreement

For a 1.0.0 release, these values must agree:

| Location | Expected value |
| --- | --- |
| `[project].version` in `pyproject.toml` | `1.0.0` |
| `__version__` in `bruhanimate/__init__.py` | `1.0.0` |
| The `bruhanimate` package entry in `uv.lock` | `1.0.0` |
| Git tag | `v1.0.0` |

The `version = 1` at the **top** of uv.lock is its file-format version, not the
package version. Dependency versions in the lockfile keep their own values.
Do not edit the lockfile by hand: run `uv lock`, then commit the updated lock.
uv retains existing compatible pins unless an upgrade is requested. The lockfile
pins contributor/CI environments; consumers install the declared dependency ranges.

Write mode validates both source assignments before writing; a failed second write
restores the first. A later locking/check failure leaves local changes reviewable
and stops before any Git operations. Fix the issue, run `uv lock`, and use --check
to retry the already prepared version.

## 3. Validate and merge dev into main

The complete local gate is:

```sh
uv run --locked python publish.py --check
```

It syncs the locked dev/docs environment and checks source versions, Ruff, the
full test suite, executable documentation examples, strict Sphinx HTML, fresh
wheel/source archives, and Twine metadata. It does not bump, commit, push, tag,
or publish. Temporary distribution outputs are removed after checking.

Review the diff, commit all intended files (including new files and uv.lock when
changed), push dev, and open a PR into main:

```sh
git status --short
git diff --check
# Stage and commit the reviewed files using your usual Git workflow.
git push origin dev
gh pr create --base main --head dev --title "Prepare bruhanimate 1.0.0"
```

The GitHub CLI command is optional; opening the PR in GitHub works too. Wait for
its CI and Documentation checks, review, and merge. Then wait for the **main
commit's** checks: lint, tests on Linux/Windows/macOS, package checks, and docs
build/deployment. A green local test run does not replace these platform checks.

**At this point the documentation is updated, but the package is not published.**
You can stop here and choose the release time later.

## 4. Push the release tag when ready

Use a clean main checkout. Confirm its HEAD is the reviewed commit whose checks
passed; if newer commits arrived after that run, wait for their checks too:

```sh
git switch main
git pull --ff-only
git status --short
git log -1 --oneline
uv lock --check
uv run --locked python publish.py --check
```

After verifying the intended version and commit, **these commands start publishing**:

```sh
git tag -a v1.0.0 -m "bruhanimate 1.0.0"
git push origin v1.0.0
```

Replace both occurrences of the version for subsequent releases. Push the specific
tag; a normal branch push does not send an unpushed tag. Do not tag dev or create
a second tag for a version already published. The workflow requires the tag
commit to be reachable from origin/main and the tag to match the source version.
It resolves the commit SHA once and checks that exact commit throughout.

### What the release workflow does

1. **Verify:** validate the tag/version and main ancestry.
2. **Check:** run the same reusable CI as PRs on the verified commit.
3. **Package:** build a fresh wheel and sdist, validate contents/metadata, install
   each, and run isolated API smoke tests without editable checkout imports.
4. **Document:** execute examples and build Sphinx with warnings treated as errors.
5. **Publish:** download the verified package artifact into a separate job and
   upload it to PyPI using Trusted Publishing with attestations.
6. **Release:** create or finish a GitHub release and attach the package archives.

The publish job does not check out or execute project code. Build/test jobs have
read-only permissions; only upload/release/Pages jobs receive their needed write
permissions. Release-time docs checks do not deploy Pages; main merges do.

uv manages environments, locking, and builds. `poetry-core` is only the PEP 517
build backend; Poetry CLI is not needed. Builds use `uv build --no-sources` so
local source overrides cannot hide broken published metadata. The PyPA action
handles uploading and generates attestations for Trusted Publishing; do not run
`uv publish` locally as an additional release step.

Historical files in dist are left intact. CI uses a fresh build/release artifact;
never upload all files from an old dist folder. Archive checks reject unexpected
files, and test/coverage reports are retained as workflow artifacts.

## 5. Verify the published package

Follow the [Release workflow](https://github.com/ethanlchristensen/bruh.animate/actions/workflows/release.yml)
and check the **publish** and **github-release** jobs, not only main's CI:

```sh
gh run list --workflow release.yml --limit 5
gh run view RUN_ID
```

Replace RUN_ID with the numeric run ID. Confirm the version on
[PyPI](https://pypi.org/project/bruhanimate/) and the corresponding
[GitHub release](https://github.com/ethanlchristensen/bruh.animate/releases).

From a separate directory outside the source checkout, test the public install
in a temporary uv environment:

```sh
uv run --no-project --python 3.13 --with bruhanimate==1.0.0 python -c "import bruhanimate; print(bruhanimate.__version__)"
uv run --no-project --python 3.13 --with bruhanimate==1.0.0 python -m bruhanimate.demos.grid_demo
```

The first command must print 1.0.0. The second is an interactive terminal check;
press q to exit. Running outside the checkout prevents Python from importing the
local source instead of the public package. Only then update downstream projects,
such as the separate Advent of Code repository, to use the published version.

## Recovery and common questions

| Symptom | Check / next step |
| --- | --- |
| Main is green, but PyPI has the old version | Look for a pushed matching release tag and a Release run. Merging alone does not publish. |
| A local tag exists, but no Release run appears | Run `git ls-remote --tags origin v1.0.0`; a local tag must be pushed. |
| Tag/version validation fails | Compare the four version locations above and confirm the tag points to the intended main commit. |
| uv reports a stale lock | Run `uv lock` on dev and commit the result with the source change. Keep `--locked` checks enabled. |
| Dependency update PRs fail before tests | Update the lockfile alongside metadata and resolve constraints together, such as Sphinx/Furo compatibility. |
| Upload waits for approval | Check the `pypi` environment's reviewers and tag deployment rules. |
| Upload authentication fails | Check the exact Trusted Publisher identity above in the bruhanimate PyPI project, including `release.yml` and the `pypi` environment. |
| Docs fail on a fresh checkout | Read the first Sphinx warning; empty local folders are not tracked by Git. Keep warnings-as-errors enabled. |

For a partial upload, prefer GitHub's **Re-run failed jobs** on the original
Release run. Retained artifacts preserve the exact checked files; existing PyPI
files are skipped so remaining files can finish. A failed GitHub-release job can
finish its draft without repeating a successful PyPI upload.

If a new run is needed, manually dispatch Release on main with the **existing** tag:

```sh
gh workflow run release.yml --ref main -f tag=v1.0.0
```

This rebuilds the tagged commit; archive timestamps may differ, so already
published PyPI files remain authoritative. An existing published GitHub release
is left intact. If artifacts expired, inspect the existing PyPI/GitHub files
before retrying. Never force-move a published tag or reuse its version for changed
code; prepare and publish a new version instead.

### Optional preparation-helper Git flags

Normally prepare on dev and review/commit manually. The helper can also prepare
an increased version from a **clean non-main branch** with explicit Git flags:

```sh
uv run --locked python publish.py 1.1.0 --write --commit --push --pr
```

Each flag requires the previous one: --commit requires --write, --push requires
--commit, and --pr requires --push plus authenticated GitHub CLI. Preflight rejects
main/master, detached HEAD, and existing changes. It stages only the two version
files and uv.lock; it never creates/pushes a release tag. Existing documentation or
code changes must be committed separately before using this optional shortcut.

### Documentation and maintenance checks

```sh
uv run --locked python scripts/check_examples.py
uv run --locked --group docs python scripts/build_docs.py
# Optional validation of external intersphinx inventories:
uv run --locked --group docs python scripts/build_docs.py --online-inventories
```

Open docs/build/html/index.html for a local preview. Default Sphinx builds do not
fetch external inventories; warnings still fail the build. Ruff checks Python,
and Python tests guard workflow YAML, release gates, permissions, pinned Actions,
and Pages PR conditions. These focused checks are not a general Actions expression
validator. CI does not install Go or compile a workflow linter.

Dependabot version-update schedules are removed, and existing bot PRs are closed
to stop their update/rebase-triggered CI runs. Update Action pins and dependencies
manually, keeping version comments and uv.lock current. Do not re-enable update
schedules without the maintainer's request. Automatic security-update PRs are
disabled separately in GitHub settings.

GitHub's generated Dependency Graph runs are separate from version-update PRs;
removing dependabot.yml does not disable them. They are controlled by the
repository's Advanced Security settings, not the normal workflow-disable API.
Normal CI, documentation and release workflows remain enabled.
