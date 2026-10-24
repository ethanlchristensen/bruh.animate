Rendering performance
=====================

Run a reproducible CPU benchmark from the repository checkout:

.. code-block:: sh

   uv run --locked python scripts/benchmark_rendering.py --output benchmark.json

The script opens no terminal, starts no worker threads, performs no network
requests, and does not sleep. It measures seeded snow, fire, plasma, Matrix,
the four-windows demo, and static panels at several viewport sizes. A separate
case simulates fire updates at 15/sec with presentation at 60/sec.

``--warmup`` defaults to 40 frames and ``--samples`` to 80 measured frames per
case. The output contains median and p95 CPU times for update, clear/draw,
presentation, and their total, plus mean encoded output bytes per frame.
Component medians need not sum to the median total. On frames without a
simulation tick, update time measures only the scheduling condition.

Presentation uses the real ``FramePresenter`` with a portable, in-memory ANSI
formatter. These measurements exclude native console writes, terminal painting,
input polling, resize polling, and Player's pacing. They are not measured FPS
or a substitute for testing a physical terminal. Run native terminal measurements
separately and identify the OS, terminal, dimensions, and font.

Comparing changes
-----------------

Use the same benchmark script, locked environment, seed, dimensions, warmup,
and sample count on both revisions. Close other CPU-heavy work and repeat runs
when differences are small. Use results to locate work, rather than imposing
machine-dependent timing assertions in unit tests. JSON output is local build
evidence; it need not be committed.

The rendering optimization comparison below used Python 3.13.7 on Windows,
240 columns by 80 rows, seed 42 for named effects, and the default sampling
parameters. The identical portable harness ran against baseline commit
``55e9336`` and the rendering fixes. Times are medians from one run per revision;
they are illustrative local measurements, not cross-platform guarantees.

.. list-table:: CPU timing comparison at 240 x 80
   :header-rows: 1

   * - Workload
     - Before (ms)
     - After (ms)
     - Speedup
   * - Plasma, complete frame
     - 23.555
     - 1.911
     - 12.3x
   * - Sixteen small panels, draw only
     - 5.729
     - 1.063
     - 5.4x
   * - Four moving windows, complete frame
     - 5.585
     - 1.907
     - 2.9x
   * - Matrix, complete frame
     - 11.562
     - 7.963
     - 1.5x

What changed
------------

* Scene skips wholly transparent rows using list comparison and writes already
  clipped cells directly into destination rows. Children still receive isolated,
  cleared buffers. No animation is assumed to be static; moving panels, custom
  drawing, overlapping layers, and resize retain their existing behavior.
* Plasma caches its two time-independent waves and evaluates the moving waves
  with NumPy, which is already a dependency. Geometry is rebuilt when dimensions
  or frequency values change. Values near palette boundaries use the original
  scalar calculation to keep visible glyphs stable across floating-point math
  implementations. Regression tests compare frames against a scalar reference.
* Matrix now paints character changes independently of its color clock. It only
  repaints changed columns on character-only ticks and reuses identical styled
  glyphs within each update. The cache expires every tick, so palette and color
  environment changes are observed on subsequent repainting. The fixed effect
  paints changes that were previously missed, so its output volume is higher;
  its before/after timings do not represent identical visible workloads.
* Unix output applies its unsupported-character fallback at the write boundary,
  including batched frames. Encodable text and ANSI styling are preserved.
  ASCII, Windows-1252, and UTF-8 regressions exercise the Unix Python path with
  mocked curses; they do not claim native Unix terminal validation.

Existing output batching and changed-cell diffing remain in place. Static panels
produce no terminal output after the initial frame, although composition still
runs. Lowering an effect's update rate reduces simulation work without reducing
presentation frequency; see :doc:`player` and :doc:`composition`.


Native terminal benchmark
-------------------------

Use the companion harness from an interactive terminal on Windows, Linux, or
macOS. It requires no additional packages and restores the Screen even if an
update, draw, or output write fails:

.. code-block:: sh

   uv run --locked python scripts/benchmark_terminal.py --effect plasma --output native-plasma.json
   uv run --locked python scripts/benchmark_terminal.py --effect four_windows --output native-windows.json

``--effect`` also offers snow, fire, and matrix. ``--samples`` defaults to 120,
``--warmup`` to 30; ``--update-every 4`` simulates 15 updates/sec against 60
presentations/sec. Execution is unpaced to measure throughput. Size comes from
the actual Screen; keep the terminal size stable throughout the run. A resize
aborts rather than mixing measurements from different sizes. stdin/stdout must
be TTYs; use ``--output`` instead of redirecting stdout. Reports print only after
the screen has been restored. Ctrl+C also restores it.

The presentation measurement includes actual Screen writes and flushes through
the OS backend. It excludes terminal-emulator/GPU display latency and does not
establish visible maximum FPS. Output byte count is null for native runs because
backend encoding, cursor handling, and transport differ. Metadata records the
platform, Python version, terminal environment, viewport, and sampling settings.

A local Windows 11 / Python 3.13.7 run through the Codex session's console/ConPTY
used the Windows Screen backend at 80 x 24, 30 warmup frames and 120 samples:

.. list-table:: Native backend timings (milliseconds)
   :header-rows: 1

   * - Workload
     - Presentation median / p95
     - Total median / p95
   * - Plasma
     - 0.175 / 0.201
     - 0.287 / 0.345
   * - Four moving windows
     - 0.150 / 0.327
     - 1.127 / 1.464

These are single-run measurements of that console transport, not Windows Terminal
rendering measurements or native Linux/macOS results. They are not a before/after
comparison with the CPU table above. Mocked tests verify cleanup, TTY refusal,
resize aborts, and timing/report plumbing separately from these native runs.
