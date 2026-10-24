Native platform checks
======================

Unit tests use recording Screens and synthetic audio. Native checks are explicit
because opening a real terminal or capturing audio requires an appropriate host.
Run from a source checkout; the default command only reports platform/dependency
metadata and does not open a device:

.. code-block:: shell

   uv run --locked python scripts/check_platform.py
   uv run --locked python scripts/check_platform.py --terminal --output terminal.json
   # Linux/macOS: creates a real pseudoterminal and exercises a size change.
   uv run --locked python scripts/check_platform.py --pty --output pty.json
   # Explicitly capture a short system-audio sample; samples are never saved.
   uv run --locked python scripts/check_platform.py --audio --seconds 3 --output audio.json

``--terminal`` requires interactive stdin/stdout and restores Screen state even on
failure. It exercises native writes, styled output, a dimension refresh, and a full
repaint. ``--pty`` additionally changes terminal dimensions and verifies resize
notification on Unix. CI runs that check on Linux and macOS and uploads the report.
These checks do not establish visual correctness, keyboard behavior, or display
latency. Windows terminal resizing should also be tried manually in the dashboard.

The audio check uses the installed optional audio backend and reports a pass only
when it receives nonzero samples and shuts down cleanly. Silence is inconclusive
and exits nonzero, as does failure. Play known audio while running it; no audio
content is retained in the JSON report. A backend importing successfully or a
mocked test passing does not establish hardware support.

Before release, manually resize the dashboard and routing demo in the terminals
you support, check focus/quit keys, and verify cursor/style restoration afterward.
Keep the platform reports with the release evidence. Record untested platforms or
devices as untested. Use :doc:`performance` for native write/flush measurements.
