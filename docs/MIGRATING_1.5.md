
## Migrating to 1.5

The browser adds search, categories, a validated settings editor, preset saving,
and MP4 export after terminal restoration. Startup/update/resize errors are now
shown in the preview when child cleanup succeeds; cleanup and draw failures still
propagate. Setting edits deliberately restart the preview with resolved settings.

`TextStyle` accepts RGB tuples and #RRGGBB colors. Its default color policy now
honors nonempty `NO_COLOR` and the presence of `ANSI_COLORS_DISABLED`; use
`enabled=True` for explicitly colored output, including deterministic exports.
The companion bruhcolor 0.0.67 provides the same controls and RGB support.
bruhanimate 1.5 requires bruhcolor >=0.0.67,<0.0.68.

Export progress callbacks run synchronously. Cancellation raises `ExportCancelled`
and preserves the destination, with cooperative checks between frames and around
encoding. A blocking encoder call cannot be interrupted by the callback.

Windows terminal commands now wait in an isolated launcher until assigned to their
owned job. The launcher uses the base interpreter to avoid virtual-environment
redirectors spawning a process before ownership. The shell receives the existing input/output pipes after the gate opens,
so rapid descendant creation cannot race initial job assignment. No window opens.

CI uses changed-file jobs: documentation-only edits skip the test matrix; test-only
edits skip documentation. Source, dependency, workflow, and unknown changes run
both. Explicit release refs and manual validation always run every gate. Required
workflows still report results; there are no workflow-level path skips.

Player.interrupted reports whether its latest run stopped on KeyboardInterrupt;
ordinary interactive playback still exits normally. Exporters use it to reject
interrupted captures, including interrupts raised inside drawing or callbacks.
