Contributing
============

Use Python 3.13 and uv 0.13.4; commit lockfile changes with dependency updates.

.. code-block:: sh

   uv sync --locked --group docs --extra export
   uv run --no-sync ruff check .
   uv run --no-sync mypy
   uv run --no-sync pytest
   uv run --no-sync python scripts/check_examples.py
   uv run --no-sync python scripts/build_docs.py
   uv run --no-sync python publish.py --check

Work on dev and open a PR targeting main. Current README/guide and site Python
examples execute headlessly through the real player. Sphinx treats warnings as
errors and disables external inventory requests by default. Open
docs/build/html/index.html to preview the local site.

The export extra enables real PNG/GIF/MP4 regressions; without it those optional
tests skip. Use :doc:`platform_checks` for opt-in native terminal/audio checks.

CI runs on Linux, Windows and macOS. It builds wheel/source distributions and
smoke-tests their installed contents without editable checkout imports.
The mypy check exercises the public discovery API, including concrete settings
return types and rejection of mismatched presets/settings.

Publishing requires a matching vMAJOR.MINOR.PATCH tag on a main-branch commit;
normal merges do not publish. Package upload uses verified artifacts in a separate
job using Trusted Publishing with attestations. Register the bruhanimate
publisher as described in :doc:`releasing`. Pages deploys only from main, while
PRs build docs for review.

The helper previews by default and requires explicit write/commit/push/PR flags.
It never creates a release tag. Follow :doc:`releasing` for the dev-to-main-to-tag
workflow and the `complete maintainer checklist
<https://github.com/ethanlchristensen/bruh.animate/blob/main/docs/RELEASING.md>`_
for setup, validation, tag commands, and retry behavior. Follow `AGENTS.md
<https://github.com/ethanlchristensen/bruh.animate/blob/main/AGENTS.md>`_ for
architecture and contribution conventions.

Use :doc:`performance` to compare rendering costs with the reproducible headless
benchmark. Keep native terminal measurements separate from CPU timings.
