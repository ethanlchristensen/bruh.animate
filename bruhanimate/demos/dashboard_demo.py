"""A layout-driven dashboard with a beam solver, live statistics and animations.

Run python -m bruhanimate.demos.dashboard_demo. Tab/Shift+Tab switches focus.
Space pauses the solver or signal; solver n steps and +/- adjusts speed.
Arrows/Page Up/Down/Home/End scroll the solver or activity log; End follows new
log messages. Signal r remixes plasma. q quits. Snow runs independently.
The original public beam fixture needs no external files, services, or tools.
"""

from bruhanimate import (
    Buffer,
    CallbackEffect,
    Column,
    Fixed,
    Flex,
    FocusGroup,
    FocusTarget,
    KeyBinding,
    KeyBindings,
    Label,
    Layer,
    LogView,
    Panel,
    PlasmaEffect,
    PlasmaSettings,
    Playback,
    ResizePolicy,
    Row,
    Scene,
    ScrollView,
    Slot,
    SnowEffect,
    SnowSettings,
    Spacer,
    StatusBar,
    TextStyle,
    draw_grid,
    play,
)

from .beam_demo import BOARD, BeamState, solve


def draw_state(state: BeamState, buffer: Buffer) -> None:
    """Draw the public fixture in the solver panel's local coordinates."""

    def glyph(cell: str, column: int, row: int) -> str | None:
        if (column, row) in state.active:
            return "\x1b[93m*\x1b[0m"
        if cell == "^":
            return "\x1b[96m^\x1b[0m"
        if (column, row) in state.visited:
            return "\x1b[92m|\x1b[0m"
        return "S" if cell == "S" else None

    draw_grid(buffer, BOARD, glyph=glyph, spacing=(2, 1))


class DashboardControls:
    """Bindings and activity state; build_scene transfers views into its layout.

    The solver ScrollView owns playback. Controls borrow the views once the
    layout owns them, and borrow the signal effect created by its panel factory.
    """

    def __init__(self, playback: Playback[BeamState]) -> None:
        self.playback = playback
        self.signal_paused = False
        self.signal: PlasmaEffect | None = None
        self.solver_view = ScrollView(
            playback,
            size=(1, 1),
            content_size=(len(BOARD[0]) * 2 - 1, len(BOARD)),
            background=None,
        )
        self.log = LogView(
            size=(1, 1),
            max_lines=200,
            wrap="character",
            style=TextStyle(foreground=252, background=235),
        )
        self.log.append("Dashboard ready. Tab selects panels.")
        self._last_steps = 0
        self._completed = False
        self.solver_target = FocusTarget(
            "solver",
            KeyBindings(
                KeyBinding("space", self.toggle_solver, description="pause"),
                KeyBinding.character("n", self.step_solver, description="step"),
                KeyBinding.character("+", self.faster, description="faster"),
                KeyBinding.character("=", self.faster),
                KeyBinding.character("-", self.slower, description="slower"),
                *self.solver_view.bindings.bindings,
            ),
        )
        self.signal_target = FocusTarget(
            "signal",
            KeyBindings(
                KeyBinding("space", self.toggle_signal, description="pause"),
                KeyBinding.character("r", self.remix_signal, description="remix"),
            ),
        )
        self.log_target = FocusTarget("log", self.log.bindings)
        self.focus = FocusGroup(self.solver_target, self.signal_target, self.log_target)

    def toggle_solver(self) -> None:
        self.playback.resume() if self.playback.paused else self.playback.pause()
        self.log.append("Solver paused" if self.playback.paused else "Solver resumed")

    def step_solver(self) -> None:
        self.playback.step()
        self.log.append("Solver step requested")

    def faster(self) -> None:
        self.playback.steps_per_second = min(240, self.playback.steps_per_second * 2)
        self.log.append(f"Solver speed: {self.playback.steps_per_second:g} steps/sec")

    def slower(self) -> None:
        self.playback.steps_per_second = max(0.25, self.playback.steps_per_second / 2)
        self.log.append(f"Solver speed: {self.playback.steps_per_second:g} steps/sec")

    def toggle_signal(self) -> None:
        self.signal_paused = not self.signal_paused
        self.log.append("Signal paused" if self.signal_paused else "Signal resumed")

    def remix_signal(self) -> None:
        if self.signal is not None:
            self.signal.shuffle_plasma_values()
            self.log.append("Signal pattern remixed")

    def observe(self, dt: float) -> None:
        """Record progress once after each scene update; never consume snapshots."""
        state = self.playback.state
        if self.playback.steps != self._last_steps and state is not None:
            self._last_steps = self.playback.steps
            self.log.append(
                f"Step {self.playback.steps}: {state.splits} splits, {state.exits} exits"
            )
        if self.playback.finished and not self._completed:
            self._completed = True
            self.log.append("Solver complete")

    def status(self) -> str:
        if self.focus.focused is self.log_target:
            return "log LIVE" if self.log.follow_tail else "log HISTORY"
        return self.focus_name()

    def focus_name(self) -> str:
        target = self.focus.focused
        return target.name if target is not None else "no panel"


class _Signal(PlasmaEffect):
    def __init__(self, buffer: Buffer, controls: DashboardControls) -> None:
        super().__init__(
            buffer, " ", PlasmaSettings(color=True, characters=False, seed=7)
        )
        self.controls = controls
        controls.signal = self

    def update(self, dt: float) -> None:
        if not self.controls.signal_paused:
            super().update(dt)


def build_scene(
    buffer: Buffer,
    playback: Playback[BeamState],
    controls: DashboardControls | None = None,
) -> Scene:
    """Allocate a solver, fixed-width sidebar, header and one-row status bar.

    Layouts reflow on resize; initially empty slots defer their factories.
    The solver panel owns a ScrollView containing playback. Supply the same
    DashboardControls here and to Player via controls.focus.handle_event.
    Input polling stays on Player; dynamic labels only read current state.
    """

    controls = controls if controls is not None else DashboardControls(playback)

    def mode() -> str:
        return (
            "Complete"
            if playback.finished
            else "Paused"
            if playback.paused
            else "Running"
        )

    def stats() -> str:
        state = playback.state
        return (
            f"Mode    {mode()}\n"
            f"Steps   {playback.steps}\n"
            f"Splits  {state.splits if state else 0}\n"
            f"Exits   {state.exits if state else 0}\n"
            f"Speed   {playback.steps_per_second:g}/s\n"
            f"Focus   {controls.focus_name()}\n"
            f"Signal  {'Paused' if controls.signal_paused else 'Running'}\n"
            "\nOriginal public fixture"
        )

    solver_panel = Panel(
        controls.solver_view,
        size=(1, 1),
        fit=True,
        title="BEAM SOLVER",
        focus=controls.solver_target,
        border_color=117,
        background=None,
    )
    log_panel = Panel(
        controls.log,
        size=(1, 1),
        fit=True,
        title="ACTIVITY LOG",
        focus=controls.log_target,
        border_color=150,
    )

    def signal_panel(local: Buffer) -> Panel:
        border = local.width() >= 3 and local.height() >= 3
        return Panel(
            effect_factory=lambda content: _Signal(content, controls),
            size=(local.width() - 2 * border, local.height() - 2 * border),
            border=border,
            fit=True,
            title="SIGNAL / 30 Hz" if border else "",
            focus=controls.signal_target,
            border_color=213,
            updates_per_second=30,
        )

    sidebar = Column(
        Slot(
            Label("LIVE STATISTICS", style=TextStyle(foreground=117, bold=True)),
            size=Fixed(1),
        ),
        Slot(
            Label(stats, style=TextStyle(background=235), overflow="ellipsis"),
            size=Fixed(9),
        ),
        Spacer(Fixed(1)),
        Slot(effect_factory=signal_panel),
    )
    layout = Column(
        Slot(
            Label(
                "BRUH DASHBOARD | Tab/Shift+Tab focus | resize freely",
                style=TextStyle(foreground=117, bold=True),
                fill=False,
            ),
            size=Fixed(1),
        ),
        Slot(
            Row(
                Slot(
                    Column(
                        Slot(solver_panel, size=Flex(3)),
                        Slot(log_panel, size=Flex(1)),
                        gap=1,
                    ),
                    size=Flex(3),
                ),
                Slot(sidebar, size=Fixed(24)),
                gap=2,
            )
        ),
        Slot(
            StatusBar(
                controls.status,
                center=controls.focus.help_text,
                right="q quit",
                style=TextStyle(foreground=231, background=24),
            ),
            size=Fixed(1),
        ),
        gap=1,
        padding=1,
    )
    snow = SnowEffect(
        Buffer(buffer.height(), buffer.width()),
        " ",
        SnowSettings(intensity=0.03, seed=42),
    )
    return Scene(
        Layer(snow, updates_per_second=15),
        layout.build(buffer),
        CallbackEffect(lambda buffer: None, update=controls.observe),
    )


def run(
    *, frames: int | None = None, fps: float = 60, on_resize: ResizePolicy = "resize"
) -> int:
    """Play the dashboard and hold the final result until quit or the frame limit."""
    playback = Playback(solve(), draw_state, steps_per_second=2)
    controls = DashboardControls(playback)
    return play(
        effect_factory=lambda buffer: build_scene(buffer, playback, controls),
        frames=frames,
        fps=fps,
        updates_per_second=60,
        on_resize=on_resize,
        event_handler=controls.focus.handle_event,
    )


if __name__ == "__main__":
    run()
