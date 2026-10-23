"""Static API contract; run mypy, do not execute this file."""

from typing import assert_type

from bruhanimate import (
    Animation,
    BindingHint,
    Buffer,
    Column,
    EventResult,
    FireEffect,
    Fixed,
    Flex,
    FocusGroup,
    FocusTarget,
    Frame,
    ImageEffect,
    KeyBinding,
    KeyBindings,
    KeyName,
    Label,
    Layer,
    LogView,
    LogWrap,
    MatrixEffect,
    Panel,
    PlasmaEffect,
    RainEffect,
    RainSettings,
    Resizable,
    ResizableAnimation,
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
    TimedOverlay,
    beam_demo,
    capture,
    dashboard_demo,
    effects,
    play,
    record,
    tv_demo,
    windows_demo,
)
from bruhanimate.effects import SnowPreset

assert_type(effects.snow.defaults(), SnowSettings)
assert_type(effects.snow.preset("light"), SnowSettings)
assert_type(effects.snow.presets(), dict[SnowPreset, SnowSettings])
assert_type(effects.static.defaults(), None)
assert_type(effects.snow.play(preset="light", duration=1), int)
effects.snow.play(settings=SnowSettings(wind=0.5), fps=60, updates_per_second=30)
play("snow", preset="light", duration=1)
play("custom_registered_effect", settings=object(), duration=1)

# warn_unused_ignores makes these checks fail if hints degrade to Any or str.
effects.snow.play(preset="storm")  # type: ignore[arg-type]
effects.snow.preset("storm")  # type: ignore[arg-type]
effects.snow.play(settings=RainSettings())  # type: ignore[arg-type]
effects.static.play(preset="light")  # type: ignore[arg-type]
SnowSettings(wind="strong")  # type: ignore[arg-type]
RainSettings(wind_direction="north")  # type: ignore[arg-type]

frames: list[Frame] = []
assert_type(capture("snow", on_frame=frames.append, frames=2, seed=42), int)
assert_type(
    effects.snow.capture(preset="light", on_frame=frames.append, frames=2, seed=42), int
)
assert_type(effects.snow.record("snow.cast", preset="light", duration=2, seed=42), int)
assert_type(record("snow", "snow.cast", frames=2), int)
assert_type(frames[0].cells, tuple[tuple[str, ...], ...])
assert_type(frames[0].time, float)
assert_type(SnowSettings(seed=42).seed, int | None)
effects.snow.capture(on_frame=frames.append, preset="storm", frames=1)  # type: ignore[arg-type]
effects.snow.record("snow.cast", settings=RainSettings(), frames=1)  # type: ignore[arg-type]
effects.snow.record("snow.cast", preset="storm", frames=1)  # type: ignore[arg-type]
SnowSettings(seed="42")  # type: ignore[arg-type]
frames[0].time = 1.0  # type: ignore[misc]

layer = Layer(ImageEffect("Snow panel"), region=(1, 2, 30, 10), updates_per_second=15)
assert_type(layer.region, tuple[int, int, int, int] | None)
assert_type(layer.updates_per_second, float | None)
overlay = TimedOverlay(ImageEffect("Ready"), duration=2, delay=0.5)
assert_type(overlay.finished, bool)
assert_type(Scene(layer, overlay).finished, bool | None)
Layer(ImageEffect("x"), region=(0, 0, "wide", 2))  # type: ignore[arg-type]
Layer(ImageEffect("x"), updates_per_second="fast")  # type: ignore[arg-type]
TimedOverlay(ImageEffect("x"), duration="brief")  # type: ignore[arg-type]
assert_type(beam_demo.run(frames=120, fps=60), int)
assert_type(tv_demo.run(frames=120, fps=60), int)
assert_type(windows_demo.run(frames=120, fps=60), int)

panel = Panel(
    ImageEffect("Snow"),
    size=(28, 8),
    position=(10, 4),
    velocity=(18, 3),
    bounds=(0, 0, 80, 24),
    bounce=True,
    border=True,
    title="Snow",
    updates_per_second=15,
)
assert_type(panel.size, tuple[int, int])
assert_type(panel.outer_size, tuple[int, int])
assert_type(panel.position, tuple[float, float])
assert_type(panel.velocity, tuple[float, float])
assert_type(panel.animation, Animation | None)
assert_type(panel.finished, bool | None)


def panel_factory(buffer: Buffer) -> Animation:
    return ImageEffect("Hello")


Panel(effect_factory=panel_factory, size=(28, 8), background=None)
Panel(ImageEffect("x"), size=("wide", 8))  # type: ignore[arg-type]
Panel(ImageEffect("x"), size=(28, 8), bounce="yes")  # type: ignore[arg-type]
Panel(ImageEffect("x"), size=(28, 8), border_color="blue")  # type: ignore[arg-type]
Panel(ImageEffect("x"), size=(28, 8), position=(0, "top"))  # type: ignore[arg-type]
Panel(ImageEffect("x"), size=(28, 8), updates_per_second="fast")  # type: ignore[arg-type]
panel.size = (10, 4)  # type: ignore[misc]

layout = Column(
    Slot(Label("Title", align="center", overflow="ellipsis"), size=Fixed(1)),
    Slot(Row(Slot(Label(lambda: "Ready"), size=Flex(2)), Spacer(), gap=1)),
    Slot(
        StatusBar("Running", right="q quit", style=TextStyle(background=24)),
        size=Fixed(1),
    ),
    gap=1,
    padding=1,
)
assert_type(layout.regions((80, 24)), tuple[tuple[int, int, int, int], ...])
assert_type(layout.build(Buffer(24, 80)), ResizableAnimation)
assert_type(Label("x").text, str)
assert_type(Fixed(4).cells, int)
assert_type(Flex(2).weight, int)
assert_type(TextStyle().foreground, int | None)
assert_type(dashboard_demo.run(frames=60), int)
Slot(effect_factory=panel_factory, size=Flex())
Label("x", align="start")  # type: ignore[arg-type]
Label("x", vertical_align="center")  # type: ignore[arg-type]
Label("x", overflow="scroll")  # type: ignore[arg-type]
Label("x", style="blue")  # type: ignore[arg-type]
StatusBar(right=123)  # type: ignore[arg-type]
Slot(Label("x"), size=2)  # type: ignore[arg-type]
Row(Label("x"))  # type: ignore[arg-type]
Flex("big")  # type: ignore[arg-type]
Fixed(1.5)  # type: ignore[arg-type]
Column(padding="wide")  # type: ignore[arg-type]
TextStyle(background="blue")  # type: ignore[arg-type]

policy: ResizePolicy = "resize"
assert_type(play("snow", on_resize=policy), int)
assert_type(effects.snow.play(on_resize="resize"), int)
resizable: Resizable = Scene()
resizable.resize((80, 24))
Panel(Label("fit"), size=(10, 2), fit=True)
play("snow", on_resize="restart")  # type: ignore[arg-type]
effects.snow.play(on_resize="restart")  # type: ignore[arg-type]
resizable.resize(("wide", 24))  # type: ignore[arg-type]
Panel(Label("fit"), size=(10, 2), fit="yes")  # type: ignore[arg-type]

snow_view = SnowEffect(Buffer(24, 80), " ")
plasma_view = PlasmaEffect(Buffer(24, 80), " ")
assert_type(snow_view.resize((100, 30)), None)
assert_type(plasma_view.resize((100, 30)), None)
snow_view.resize(("wide", 30))  # type: ignore[arg-type]
plasma_view.resize((100, "tall"))  # type: ignore[arg-type]

fire_view = FireEffect(Buffer(24, 80), " ")
rain_view = RainEffect(Buffer(24, 80), " ")
matrix_view = MatrixEffect(Buffer(24, 80), " ")
assert_type(fire_view.resize((100, 30)), None)
assert_type(rain_view.resize((100, 30)), None)
assert_type(matrix_view.resize((100, 30)), None)
fire_view.resize(("wide", 30))  # type: ignore[arg-type]
rain_view.resize((100, "tall"))  # type: ignore[arg-type]
matrix_view.resize((100,))  # type: ignore[arg-type]
assert_type(effects.fire.play(on_resize="resize"), int)
assert_type(effects.rain.play(on_resize="resize"), int)
assert_type(effects.matrix.play(on_resize="resize"), int)

key: KeyName = "space"
bindings = KeyBindings(
    KeyBinding(key, lambda: None, description="pause"),
    KeyBinding.character("q", quit=True),
)
target = FocusTarget("solver", bindings)
focus = FocusGroup(target, next_key="tab", previous_key="shift+tab", wrap=False)
Panel(Label("Focus"), size=(10, 2), focus=target, focus_border_color=117)
assert_type(bindings.hints(), tuple[BindingHint, ...])
assert_type(bindings.bindings, tuple[KeyBinding, ...])
assert_type(bindings.dispatch(32), EventResult)
assert_type(focus.handle_event(32), bool)
assert_type(focus.focused, FocusTarget | None)
assert_type(focus.focus("solver"), bool)
assert_type(focus.help_text(), str)
assert_type(target.available, bool)
assert_type(target.focused, bool)
assert_type(focus.move("previous"), None)
KeyBinding("spaec", lambda: None)  # type: ignore[arg-type]
KeyBinding("space", lambda: True)  # type: ignore[arg-type]
FocusGroup(next_key="forward")  # type: ignore[arg-type]
focus.move("back")  # type: ignore[arg-type]
Panel(Label("x"), size=(4, 2), focus="solver")  # type: ignore[arg-type]
Panel(Label("x"), size=(4, 2), focus_border_color="blue")  # type: ignore[arg-type]

wrapping: LogWrap = "character"
log = LogView(
    size=(40, 8),
    max_lines=200,
    wrap=wrapping,
    follow_tail=True,
    style=TextStyle(foreground=117),
    fill=True,
)
assert_type(log.append("Ready"), None)
assert_type(log.lines, tuple[str, ...])
assert_type(log.line_count, int)
assert_type(log.max_lines, int)
assert_type(log.wrap, LogWrap)
assert_type(log.follow_tail, bool)
assert_type(log.at_bottom, bool)
assert_type(log.offset, tuple[int, int])
assert_type(log.content_size, tuple[int, int])
assert_type(log.bindings, KeyBindings)
assert_type(log.resize((50, 9)), None)
assert_type(log.scroll_by(dy=-1), None)
assert_type(log.scroll_to((0, 3)), None)
assert_type(log.page_down(), None)
FocusTarget("log", log.bindings)
scroll = ScrollView(
    Label("Large canvas"), size=(40, 8), content_size=(100, 50), background=None
)
assert_type(scroll.animation, Animation)
assert_type(scroll.finished, bool | None)
assert_type(scroll.size, tuple[int, int])
assert_type(scroll.set_content_size((120, 60)), None)
assert_type(scroll.bindings, KeyBindings)
scrollable_animation: ResizableAnimation = scroll
log_animation: ResizableAnimation = log
LogView(size=(4, 2), wrap="word")  # type: ignore[arg-type]
LogView(size=(4, 2), max_lines="lots")  # type: ignore[arg-type]
log.scroll_by(dy="up")  # type: ignore[arg-type]
log.follow_tail = "yes"  # type: ignore[assignment]
log.lines = ()  # type: ignore[misc]
scroll.set_content_size((2.5, 2))  # type: ignore[arg-type]
ScrollView("text", size=(4, 2), content_size=(8, 4))  # type: ignore[arg-type]
