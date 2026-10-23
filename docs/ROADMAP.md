# bruhanimate improvement roadmap

Drafted October 22, 2026, from a review of the current checkout and the Advent of Code 2025 Day 7 animation.

## Goal

Make bruhanimate dependable and make custom animations easy to start. Use Screen / Buffer / Animation / Player with composable scenes. The authorized 1.0 major release removes the old renderer hierarchy and compatibility adapters.

For Advent of Code, users should primarily write **how their puzzle progresses** and **how that state looks**. The library should handle terminal setup, playback, coordinates, composition, and cleanup. Custom branching, beam routing, and visual storytelling will still require custom code.

This is a proposed backlog, not an implementation specification. API names below are provisional. Deliver small, reviewable changes; built-in effects and demos migrate to the new contract as part of 1.0.

For the researched architecture direction, alternatives, lifecycle/timing contracts, and compatibility approach, see [Effect and playback design proposal](DESIGN_PROPOSAL.md).

## Evidence and starting point

- The existing suite passes: 27 tests, with 26% overall coverage in the reviewed Windows environment.
- Additional review checks exercised 312 effect/preset/buffer-size combinations for up to 12 frames each, with audio capture disabled. Nine combinations failed. These were exploratory checks, not committed regression tests.
- Core strengths to preserve: independent effect buffers, changed-cell presentation, batched terminal output, frame-budget accounting, typed settings, and discoverable presets.
- The referenced Day 7 `animate.py` is 750 lines. Its launch function is about 47 lines, but much of the file implements legitimate puzzle behavior and visual design. Reducing total file length is not the primary success measure.
- Real terminal appearance, physical audio capture, and every supported operating system still need validation.

## Implementation progress

October 22, 2026: F1-F3, U1, and the initial U2 runner are implemented.
The 1.0.0 preparation migrates all built-in effects to update/draw, removes old
renderers/adapters, adds Scene/Layer/ImageEffect, and moves shell ownership into
TerminalEffect. All 25 demos use Player, including configuration showcases and the new grid search.
See [the player guide](PLAYER.md), [solver playback guide](SOLVER_PLAYBACK.md),
and [1.0 migration guide](MIGRATING_1.0.md).

Verification: **639 tests pass** on Windows/Python 3.13.7, with 96% player
coverage, 98% Playback coverage, 99% grid coverage, and 100% scene coverage. Ruff and git diff whitespace checks pass.
All 25 demos and every registered preset run at 24x80, 3x5, and 1x1.
Ten current-API documentation examples execute through the real Player with a
recording Screen. Sphinx HTML builds with warnings treated as errors (remote
intersphinx inventories disabled for offline verification). The 1.0.0 wheel and
source archive build successfully; isolated wheel imports, public exports,
Playback/grid/solver execution, type marker, and removed-module exclusions are verified. A native Windows console
grid playback smoke test presents twelve frames and restores the terminal. Audio capture
is stubbed in tests; Unix backend tests use mocks. Real subprocess tests cover
command/readers and Windows descendant-process shutdown. Physical audio and
native Unix terminals remain manual checks. The release is prepared locally,
not published.

Compatibility notes for this batch:

- Partial clears clip to buffer bounds; zero or negative region sizes do nothing. Negative buffer dimensions and mismatched buffer copies/overlays now raise `ValueError`.
- Rain retains its 0-999 intensity scale. The default is now 200; drizzle/storm/thunderstorm/monsoon use 100/600/700/900. Every positive intensity can generate rain, and zero disables new drops when swells are off. The rain demo starts at 700.
- Snow accepts probabilities down to zero, so the light preset's 0.005 intensity is honored and zero disables new flakes. Existing flakes continue to move.
- Small positive buffers clip lightning/fireworks and avoid radial audio division by zero. This does not establish support for zero-sized effect canvases.

## What the Advent of Code example tells us

Reference: `AdventOfCodeSolutions/2025/day07/animate.py` in the user's separate repository. Treat it as a use case; this roadmap does not require editing that repository.

| Current responsibility | Evidence in Day 7 | Intended owner |
| --- | --- | --- |
| Terminal and renderer setup | `animate()` opens through `Screen.show`, constructs a static renderer, then replaces `renderer.effect` | Library runner |
| Buffer allocation | Separate screen-sized buffers for the puzzle, fireworks, and twinkles | Runner and composition layer |
| Puzzle-to-screen layout | Repeated `px + board_spacing * x` and `py + y` calculations | Grid/viewport helper |
| Playback speed | `effect_halt`, `second_effect_halt`, twinkle counters, pulse counters, and modulo checks | Playback clock and reusable timing helpers |
| Background composition | Nested `second_effect` use and manual full-screen copying with exclusion checks | Ordered layers and clipping/masks |
| Restoring old pixels | Ripple, connector, beam, and erased-position bookkeeping | Composition and transient overlays, where practical |
| Puzzle progression | Splitters, path counts, branch traversal, and completion rules | Puzzle code |
| Visual choices | Beam glyphs, colors, pulses, evergreen completed paths, and celebrations | Puzzle code, assisted by optional drawing helpers |

The first usability win should be removing the placeholder renderer and replacement-effect pattern. A full scene system is not a prerequisite for that improvement.

## Priority 0: repair the foundation

### F1. Preserve buffer invariants

- [x] Clip partial clears to the requested rectangle and buffer bounds. Define behavior for negative coordinates and nonpositive dimensions.
- [x] Distinguish omitted width/height (`None`) from explicitly supplied zero.
- [x] Ensure clearing, copying, scrolling, and overlays preserve the declared rectangular dimensions. Reject incompatible buffer dimensions clearly.
- [x] Add behavioral tests for partial clears at edges, zero-sized regions, negative origins, oversized regions, and row independence.

**Acceptance:** `Buffer(2, 3).clear_buffer(x=2, w=3, h=1)` cannot expand a row; clearing from `y=1` with no height cannot index past the bottom. Tests verify the chosen clipping behavior and unchanged cells outside the region.

### F2. Make built-in defaults and presets trustworthy

- [x] Repair the `stars` and `gol` color presets, which reference an unavailable `COLOR` palette.
- [x] Fix default rain and drizzle: their intensity produces a population containing only spaces. Reconcile preset values with the documented intensity scale.
- [x] Reconcile the snow `light` preset with the constructor's minimum intensity.
- [x] Handle small buffers deliberately, including narrow lightning, tiny fireworks, and radial audio rendering. Choose graceful clipping, a fallback, or an explicit minimum-size error.
- [x] Add parameterized smoke tests over every registered preset and a representative set of dimensions. Stub audio acquisition rather than opening devices in CI.
- [x] Add selected behavior assertions so a successful render call cannot conceal a permanently blank effect. Use controlled randomness for probabilistic behavior.

**Acceptance:** all supported preset/size combinations render without unexpected exceptions; unsupported sizes fail clearly. Known patterns and deterministic fixtures verify representative effect behavior.

### F3. Make imports and resource ownership predictable

- [x] Remove shell commands from demo module import paths. A fresh package import previously invoked `os.system(" ")` 22 times.
- [x] Preserve documented demo access through an import-safe approach; establish a deprecation path if any public import changes.
- [x] Define effect startup/shutdown hooks with harmless defaults for ordinary effects. Avoid starting capture resources merely to configure an effect.
- [x] Ensure player shutdown releases owned effects on completion, interruption, resize, and exceptions. Specify ownership when an effect is supplied externally.
- [x] Make audio shutdown idempotent, wait for worker termination with a bounded timeout, and release Windows audio resources through structured cleanup, including initialization failures.
- [x] Define equivalent cleanup for subprocess streams and workers in `TerminalEffect`.

**Acceptance:** import has no shell/terminal/device side effects. A fake capture worker is no longer alive after its owning runner exits. Failure during startup or rendering still restores terminal state and releases resources.

## Priority 1: make a custom animation easy to launch

### U1. Accept custom effects directly

- [x] Allow the shared player to receive an effect factory, with an allocated buffer supplied by the player. Preserve the existing named-effect path and settings/presets.
- [x] Define precedence explicitly: callers select either an effect or a custom factory; ambiguous combinations raise a useful error.
- [x] Make runtime validation consult the registry so newly registered native effects work with the player.
- [x] Define the effect interface using an enforced abstract base class or a protocol. Include lifecycle capabilities introduced in F3.
- [x] Keep initialization errors attributable to the user's factory and restore the terminal when construction fails.

**Acceptance:** a custom effect can run without constructing a dummy static effect, replacing `renderer.effect`, or manually matching buffer dimensions. Existing named-effect examples still work.

### U2. Add a small public runner

- [x] Add one convenience entry point that owns `Screen.show`, buffer creation, rendering, FPS configuration, shutdown, and basic completion behavior.
- [ ] Add duration limits. Source-exhaustion hold/exit, frame limits, and user-controlled quit are implemented.
- [x] Make the shared player prompt-free and allow headless execution through a borrowed recording Screen.
- [x] Keep the low-level API available for advanced applications.
- [x] Provide a custom-effect starter example; the AoC factory sketch below resolves input paths relative to the script rather than the current working directory.

**Available runner API, with the user's puzzle class supplied by their application:**

```python
from pathlib import Path
from bruhanimate import play

data_file = Path(__file__).with_name("datasmall")

def create_effect(buffer):
    return AdventOfCodeDay07Effect(
        buffer=buffer,
        background=" ",
        data_file=data_file,
        board_spacing=2,
        branch_mode=True,
    )

play(effect_factory=create_effect, fps=60)
```

The existing puzzle class is supplied by the application. This first step simplifies launching it; later steps simplify its timing and rendering internals.

**Acceptance:** a basic custom effect needs roughly 15 lines or fewer of launch code, excluding imports and the effect implementation. A user can copy the starter and immediately replace its drawing logic.

## Priority 2: support solver playback

### A1. Separate puzzle progression from rendering

- [x] Add native Playback for a lazy snapshot iterator and drawing callback without a BaseEffect subclass.
- [x] Start with state snapshots; add an event/delta adapter only when examples demonstrate a need. Specify whether yielded mutable data is copied or must remain unchanged by the producer.
- [x] Keep parsing and puzzle rules independent of terminal access. File-loading errors should remain clear application errors rather than silently selecting different input.
- [x] Stop consuming states when playback stops. Do not eagerly materialize the entire trace.
- [x] Retain one current snapshot, bound catch-up calls, and document synchronous next() responsiveness. Worker execution remains deferred.
- [x] Document sampling, step limits, and aggregated progress for enormous search spaces. Day 7's eager enumeration of every branch can grow exponentially; faster rendering cannot solve that.

**Acceptance:** the same state producer can run as an ordinary solver, in a headless test, and in an animation. Test with a small public fixture that does not depend on a private AoC input file.

### A2. Add a playback clock and basic controls

- [x] Separate displayed FPS from logical simulation ticks per second; built-in settings retain documented tick units.
- [x] Support solver pause/resume, queued single steps, faster/slower playback, and quit through normalized Screen input. Unrelated backgrounds keep updating.
- [x] On resume, discard paused wall-clock time instead of applying a burst of catch-up steps. Bound catch-up work when rendering falls behind.
- [x] Add hold/exit completion after final presentation, finite-child Scene completion, and status callbacks for optional messages.
- [ ] Add small reusable duration/progress helpers for pulses and temporary overlays. Larger timeline/choreography APIs can wait.

**Acceptance:** changing presentation from 30 to 60 FPS preserves logical puzzle progress over the same simulated duration. Tests use a fake clock and input source rather than real sleeps.

## Priority 3: remove repeated layout and composition work

### V1. Introduce a grid/viewport helper

- [x] Provide board-to-screen conversion, centering, horizontal/vertical cell spacing, offsets, and clipping in one reusable object.
- [x] Define oversized-board behavior: initially clip within a viewport with an explicit camera offset. Add automatic following or fitting only if useful.
- [x] Provide bulk grid drawing with a user-supplied glyph/style mapping, plus basic text, paths, and markers.
- [x] Specify rectangular/ragged input handling and empty-grid behavior.
- [x] Define a cell-width policy. Day 7 uses Unicode box drawing and decorative glyphs, so string length alone is not a reliable terminal-width contract. Begin with supported single-cell glyphs and document limitations.

**Acceptance:** Day 7's drawing code can call one coordinate transform instead of repeating `px`, `py`, and spacing arithmetic. Tests cover boards smaller and larger than the viewport, including origins at zero and negative offsets.

### V2. Compose independent layers

- [x] Add Scene/Layer composition for background effects, transient overlays, and status text; puzzle drawing can use CallbackEffect.
- [x] Define None transparency and opaque spaces, with explicit per-layer space transparency.
- [ ] Support clipped regions and a simple mask when a rectangular board region is insufficient.
- [ ] Give layers independent update rates using A2's clock. Recompose from their latest buffers before the existing changed-cell presentation step.
- [x] Establish one lifecycle owner per animation; Scene replaces nested second_effect ownership. Direct duplicate children are rejected; callers must avoid sharing across owners.
- [ ] Provide optional path-pulse and expanding-ripple helpers after two examples confirm their reusable parameters. Keep puzzle completion decisions in application code.

**Acceptance:** a disappearing ripple or pulse reveals the correct underlying board/background without application code manually repainting those cells. Twinkles, fireworks, board, and status text compose independently. An unchanged final image emits no additional cell writes.

## Priority 4: make examples and releases dependable

### Q1. Expand behavior and platform verification

- [x] Test rendering through a recording Screen, including moving overlays and changed-cell suppression.
- [ ] Test Game of Life fixtures, finite numerical simulation values, cleanup, and registry extension behavior.
- [x] Configure Python 3.13 CI on Windows, Linux and macOS. Local Windows verification passes; the first remote runs still need to verify Linux/macOS runners.
- [x] Align declared Python support, Ruff target, and current tests on Python 3.13.
- [x] Commit uv.lock for contributor/CI resolution; consumer installations continue using distribution dependency ranges.
- [x] Fix the reported Ruff whitespace error and keep lint checks passing.

### Q2. Reconcile the public API and documentation

- [x] Correct README image support: get_image retrieves bundled ASCII art.
- [x] Remove the unfinished water placeholder from the API and catalog.
- [x] Correct Buffer examples and public exports, including TerminalEffect and stale utility names.
- [ ] Define validation rules for zero coordinates, black color code `0`, empty text/images, settings ranges, and malformed inputs. Raise errors at the public boundary instead of incidental exceptions deep in rendering.
- [x] Execute implemented README/player/solver-guide Python examples through a recording Screen; historical 0.2.x snippets are intentionally excluded.
- [x] Add a short guide for custom effects, followed by a solver-playback guide and a layered-animation guide. Explain where each approach is appropriate.
- [x] Derive documentation version metadata from the package. The Sphinx site links the implemented player/migration guides; this backlog remains repository Markdown.

**Acceptance:** documented examples match working APIs and advertised features. A new user can follow the custom-animation path without first studying a built-in effect implementation.

## Priority 5: measure, simplify, and extend

- [ ] Profile representative sparse, full-screen, particle, and composed scenes at several terminal sizes. Separate simulation, composition, diffing, color conversion, and terminal-write costs.
- [ ] Remove measured waste, such as clearing a buffer immediately before fully overwriting it or scanning an empty overlay every frame. Preserve correctness tests before changing buffer rotation.
- [ ] Consolidate repeated palette helpers and split large audio/fireworks modules by responsibility while preserving public imports.
- [ ] Consider spatial neighbor indexing for larger boid counts only if the all-pairs calculation is a measured bottleneck.
- [ ] Introduce explicit random seeds/RNG injection for repeatable effects, covering both Python and NumPy randomness.
- [ ] Add deterministic headless frame capture first, followed by an optional terminal recording or image/video exporter. Keep optional export dependencies separate from normal installation.
- [ ] Consider a demo browser/CLI after the custom-animation workflow is stable.

**Acceptance:** optimization claims come with reproducible measurements; seeded fixtures produce repeatable frames. Export uses the same rendering pipeline and requires no attached terminal or private puzzle data.

## Suggested delivery sequence

| Change | Scope | Depends on |
| --- | --- | --- |
| 1 | Buffer invariant fixes and failing regression cases | F1 |
| 2 | Preset/default repairs and representative effect smoke tests | F2 |
| 3 | Import-safe demos and explicit resource lifecycle | F3 |
| 4 | Custom effect factory, registry validation, and convenience runner | U1-U2; lifecycle contract from F3 |
| 5 | Lazy state playback, independent step rate, and basic controls | A1-A2; runner |
| 6 | Grid viewport and drawing helpers | V1; buffer fixes |
| 7 | Minimal layer composition and transient overlays | V2; lifecycle and clock |
| 8 | A small Day 7-inspired reference animation and migration guide | Playback, viewport, layers |

Q1/Q2 work accompanies the changes it verifies; it should not be postponed until every API feature exists. Profiling and export follow demonstrated needs. Each row can be split into smaller pull requests.

## Validate the direction with two examples

1. **Minimal solver visualization:** animate a small grid traversal from a lazy state iterator, with no subclass, manual buffer allocation, or terminal setup. Include a status line and pause/step controls.
2. **Day 7-inspired showcase:** preserve custom splitter/beam rules while moving launch setup, coordinates, update rates, background layers, and transient restoration into library helpers. Use a small independently created fixture. Do not copy the original 750-line animation wholesale into the core library.

Record launch-code size, framework-only bookkeeping removed, setup steps required, and which helpers both examples actually use. Aim for roughly 25 lines or fewer of composition/launch code in the showcase, excluding solver logic, visual rules, and style definitions. Revise that target if it encourages hidden complexity.

## Decisions to make during implementation

- Choose the public runner name and custom-factory signature using a working example before committing the API.
- Decide whether restart reconstructs the state iterator/effects through factories. Backward seeking and arbitrary rewind are deferred because they require replayable input or retained history.
- Define lifecycle ownership, resize behavior, and transparency before exposing layers broadly. The initial runner may stop cleanly on resize; reflow/reconstruction is a separate capability.
- Migrate built-in effects directly for 1.0; tick-based algorithms retain their own counters and use an explicit update rate. Do not preserve old renderer APIs.
- Keep puzzle-specific rules outside the framework. Promote a helper only when its behavior is useful across multiple animations.

## Recommended starting slice

F1-F3, U1, initial U2, A1, core A2 controls/completion, V1, and basic V2 composition are implemented. Playback and GridViewport are validated with a public BFS maze solver and composed demo. Next validate a second puzzle (such as a Day 7-inspired beam fixture) before adding masks, general layer clocks, or reusable pulses. Duration limits, export, and resize reconstruction remain open.

## Release pipeline follow-up

Tag-only publication replaces automatic publishing on a version-file merge.
Release checks validate stable versions/TOML/AST, matching tags, main ancestry,
archive metadata, installed wheel/sdist APIs, and documentation. Upload and
GitHub release permissions are isolated from build/test jobs. Pages PR builds
cannot deploy. The local helper previews by default and exposes explicit write,
commit, push and PR flags. See [RELEASING.md](RELEASING.md) and [AGENTS.md](../AGENTS.md).
Main-branch CI and Pages deployment passed after the initial setup fixes. The
v1 package upload and publishing credentials remain to be exercised by a tagged
release; changing source/workflows does not itself publish a package.

Release follow-up verification: all 641 tests pass, including 37 release-tool
cases. Ruff, uv lock validation, current executable examples, strict
Sphinx, archive validation and Twine checks pass. Both wheel and sdist were
installed into separate build directories and passed isolated API smoke tests.
Package metadata now uses the standard project table and points to the verified
ethanlchristensen/bruh.animate repository and Pages site. Historical dist archives were preserved;
release gates use clean output directories rather than uploading the entire
historical dist folder. The main CI run checked Linux, Windows, and macOS;
PyPI publication is a separate tag-triggered workflow.

uv now manages contributor/CI environments, standard dependency groups and builds.
`uv.lock` replaces poetry.lock, with the uv version pinned in pyproject.toml.
Release write mode refreshes and includes the lockfile; check mode rejects stale
locks. The PyPA upload action still generates Trusted Publishing attestations.
The uv-built wheel contains the same package files as the previous build, and
both the wheel and rebuilt sdist passed installed-package checks in a fresh uv
environment. A temporary version-bump probe confirmed that refreshing uv.lock
retains dependency pins. The existing local .venv was left intact during testing.

The first remote CI run exposed two setup issues: compiling actionlint triggered
a failing Go toolchain download, and Sphinx referenced an empty local `_static`
directory absent from Git. CI now uses Ruff and the existing Python workflow
guards without installing Go. Sphinx relies on theme assets and no longer
requires that unused directory. Documentation was checked from a copy of tracked
files to exercise the same directory layout as a fresh checkout.

## Documentation and release onboarding

The README now introduces the v1 building blocks, executable examples, and learning
paths. The Sphinx site has Getting started, Core concepts, and Release process
pages before the API reference. Its Python examples join the Markdown examples
in the headless execution check (18 examples). The release checklist documents
dev → main → green CI → version tag, all version/lockfile locations, the current
Trusted Publisher identity, public-install verification, and recovery steps.
Documentation changes deploy with a main merge; package publication still requires
an explicitly pushed matching tag.
