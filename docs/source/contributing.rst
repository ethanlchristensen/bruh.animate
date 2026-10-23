Contributing
============

Use Python 3.13 and uv 0.13.4; commit lockfile changes with dependency updates.

.. code-block:: sh

   uv sync --locked --group docs
   uv run --locked ruff check .
   uv run --locked pytest
   uv run --locked python scripts/check_examples.py
   uv run --locked --group docs python scripts/build_docs.py
   uv run --locked python publish.py --check

Work on dev and open a PR targeting main. Current README/guide and site Python
examples execute headlessly through the real player. Sphinx treats warnings as
errors and disables external inventory requests by default. Open
docs/build/html/index.html to preview the local site.

CI runs on Linux, Windows and macOS. It builds wheel/source distributions and
smoke-tests their installed contents without editable checkout imports.

Publishing requires a matching vMAJOR.MINOR.PATCH tag on a main-branch commit;
normal merges do not publish. Package upload uses verified artifacts in a separate
job. Trusted Publishing is used when PYPI_TOKEN is absent; an existing token
continues to work. Pages deploys only from main, while PRs build docs for review.

The helper previews by default and requires explicit write/commit/push/PR flags.
It never creates a release tag. Follow :doc:`releasing` for the dev-to-main-to-tag
workflow and the `complete maintainer checklist
<https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md>`_
for setup, validation, tag commands, and retry behavior. Follow `AGENTS.md
<https://github.com/ethanlchristensen/bruh.animate/blob/main/AGENTS.md>`_ for
architecture and contribution conventions.
