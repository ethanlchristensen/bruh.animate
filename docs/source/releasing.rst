Release process
===============

Develop on dev, merge into main, wait for green checks, and push a version tag
when ready to publish. A main merge deploys the documentation; it does not upload
a package. This page covers the workflow; the repository's `maintainer checklist
<https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md>`_
also includes recovery details and optional preparation-helper Git flags.

Configure publishing once
-------------------------

The repository is ``ethanlchristensen/bruh.animate``. Set GitHub Pages' source to
GitHub Actions and configure the ``pypi`` environment to allow release tags.
Protect main with CI and Documentation checks.

Uploads use Trusted Publishing (OIDC) with attestations. Before the next release,
register these fields in PyPI's bruhanimate project publishing settings. The
bruhcolor project's publisher does not authorize bruhanimate uploads.

.. list-table:: Trusted Publisher identity
   :header-rows: 1

   * - Field
     - Value
   * - GitHub owner
     - ``ethanlchristensen``
   * - Repository
     - ``bruh.animate``
   * - Workflow
     - ``release.yml``
   * - Environment
     - ``pypi``

The workflow does not read ``PYPI_TOKEN``. After a successful Trusted Publishing
release, remove the unused repository/environment secret and revoke the old
PyPI token if no other workflow uses it.
These settings are external to the source checkout. Follow the `PyPI setup guide
<https://docs.pypi.org/trusted-publishers/adding-a-publisher/>`_ for account setup.

Prepare and validate on dev
---------------------------

Use Python 3.13 and the pinned uv version (currently 0.13.4):

.. code-block:: sh

   git switch dev
   git pull --ff-only
   uv sync --locked --group docs
   uv lock --check
   uv run --locked python publish.py --check

If the version is already prepared, --check validates it without bumping it.
For a future version, preview, then explicitly write the increase:

.. code-block:: sh

   uv run --locked python publish.py 1.1.0
   uv run --locked python publish.py 1.1.0 --write

Write mode updates both source version assignments, refreshes uv.lock, and runs
local checks. Review and commit the intended changes, including the lockfile.
The helper never creates a release tag. Update public examples and migration
notes when behavior changes.

.. list-table:: Agreement for a 1.0.0 release
   :header-rows: 1

   * - Location
     - Value
   * - pyproject.toml project.version
     - ``1.0.0``
   * - bruhanimate.__version__
     - ``1.0.0``
   * - bruhanimate entry in uv.lock
     - ``1.0.0``
   * - Git tag
     - ``v1.0.0``

The top-level ``version = 1`` in uv.lock describes the lockfile format. Leave it
alone; refresh the lock with ``uv lock`` instead of editing it by hand. Stable
MAJOR.MINOR.PATCH release versions are supported; prerelease suffixes are not.

Merge, then choose the release time
-----------------------------------

Push dev and open a PR into main. Wait for CI/docs, review, and merge. Wait again
for the merged main commit's checks: Linux/Windows/macOS tests, lint, packages,
and documentation build/deployment. You can stop here and publish later.

When ready, use a clean main checkout and confirm its HEAD is the intended green
commit. Replace the version below for subsequent releases:

.. code-block:: sh

   git switch main
   git pull --ff-only
   git status --short
   git log -1 --oneline
   uv lock --check
   uv run --locked python publish.py --check

These final commands start the publishing workflow:

.. code-block:: sh

   git tag -a v1.0.0 -m "bruhanimate 1.0.0"
   git push origin v1.0.0

The tag must match the package version and point to a commit reachable from
origin/main. A local tag must be pushed; a normal branch push does not send it.

What runs and how to verify it
------------------------------

The Release workflow validates the tag and main ancestry, runs CI and strict docs
for the exact commit, and builds a wheel/sdist. Each archive is installed and
smoke-tested without editable checkout imports. Only after every gate succeeds
does a separate upload job publish the verified artifacts, followed by a GitHub
release with package assets. Release docs checks do not deploy Pages.

.. code-block:: sh

   gh run list --workflow release.yml --limit 5
   gh run view RUN_ID

Replace RUN_ID with the numeric run ID. Check both publish and github-release jobs,
then check `PyPI <https://pypi.org/project/bruhanimate/>`_ and
`GitHub releases <https://github.com/ethanlchristensen/bruh.animate/releases>`_.
Main's green CI badge alone does not confirm package publication.

From a separate directory outside the source checkout, verify the public install:

.. code-block:: sh

   uv run --no-project --python 3.13 --with bruhanimate==1.0.0 python -c "import bruhanimate; print(bruhanimate.__version__)"
   uv run --no-project --python 3.13 --with bruhanimate==1.0.0 python -m bruhanimate.demos.grid_demo

Confirm the printed version, try the interactive demo, and press q to exit.
Then update downstream applications to the published dependency version.

Retry a partial failure
-----------------------

Prefer Re-run failed jobs on the original release run to reuse its verified
artifacts. Existing PyPI files are skipped and a GitHub-release draft can finish.
For a new run using the existing tag:

.. code-block:: sh

   gh workflow run release.yml --ref main -f tag=v1.0.0

The new run rebuilds the tagged commit. Do not force-move a published tag or reuse
a published version for code changes; prepare a new version. For missing tags,
stale locks, authentication errors, and expired artifacts, use the full
`recovery checklist
<https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md#recovery-and-common-questions>`_.
