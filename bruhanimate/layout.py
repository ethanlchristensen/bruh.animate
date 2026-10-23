"""Declarative row/column allocation with explicit sizing and child ownership."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Literal

from .bruhutil.bruhffer import Buffer
from .grid import _glyph
from .keyboard import _set_visible
from .panel import Panel
from .player import Animation, CallbackEffect, ResizableAnimation
from .resize import _resize, _size
from .scene import Scene


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


@dataclass(frozen=True)
class Fixed:
    """Request a non-negative number of cells along the container's main axis."""

    cells: int

    def __post_init__(self) -> None:
        _integer(self.cells, "cells")


@dataclass(frozen=True)
class Flex:
    """Share remaining cells in proportion to a positive integer weight."""

    weight: int = 1

    def __post_init__(self) -> None:
        _integer(self.weight, "weight", 1)


@dataclass(frozen=True)
class Slot:
    """One owned animation or nested layout, with explicit main-axis sizing.

    Supply exactly one of content or effect_factory. Factories run at startup
    with the allocated local Buffer, only for nonempty slots. Size defaults to
    Flex(1). Factories must return fresh Animation instances, not shared children.
    """

    content: Animation | Row | Column | None = None
    size: Fixed | Flex = field(default=Flex(), kw_only=True)
    effect_factory: Callable[[Buffer], Animation] | None = field(
        default=None, kw_only=True
    )

    def __post_init__(self) -> None:
        if (self.content is None) == (self.effect_factory is None):
            raise ValueError("Slot requires exactly one of content or effect_factory")
        if self.content is not None and not isinstance(
            self.content, (Animation, Row, Column)
        ):
            raise TypeError("Slot content must be an Animation, Row, or Column")
        if self.effect_factory is not None and not callable(self.effect_factory):
            raise TypeError("effect_factory must be callable")
        if not isinstance(self.size, (Fixed, Flex)):
            raise TypeError("size must be Fixed or Flex")


@dataclass(frozen=True)
class Spacer:
    """An unpainted layout slot; defaults to Flex(1), or use Fixed(cells)."""

    size: Fixed | Flex = Flex()

    def __post_init__(self) -> None:
        if not isinstance(self.size, (Fixed, Flex)):
            raise TypeError("size must be Fixed or Flex")


class _Layout:
    _axis: Literal["row", "column"] = "row"

    def __init__(
        self,
        *children: Slot | Spacer,
        gap: int = 0,
        padding: int = 0,
        background: str | None = None,
    ) -> None:
        if any(not isinstance(child, (Slot, Spacer)) for child in children):
            raise TypeError("Layout children must be Slot or Spacer instances")
        _integer(gap, "gap")
        _integer(padding, "padding")
        if background is not None:
            _glyph(background)
        self._children, self._gap, self._padding = children, gap, padding
        self._background = background
        self._used = False

    def regions(self, size: tuple[int, int]) -> tuple[tuple[int, int, int, int], ...]:
        """Inspect (x, y, width, height) for each child without acquiring anything.

        Size is the available width/height. Uniform padding and gaps reserve
        space first. Fixed requests then consume space in declaration order;
        Flex children share the remainder using largest remainders, with ties
        going to earlier children. The cross axis fills the padded extent.
        Zero-area regions may have origins outside size when gaps cannot fit.
        """
        if not isinstance(size, tuple) or len(size) != 2:
            raise TypeError("size must be a (width, height) tuple")
        for value in size:
            _integer(value, "dimension")
        horizontal = self._axis == "row"
        main, cross = size if horizontal else (size[1], size[0])
        remaining = max(
            0, main - 2 * self._padding - self._gap * max(0, len(self._children) - 1)
        )
        extents = [0] * len(self._children)
        flexible = []
        for index, child in enumerate(self._children):
            if isinstance(child.size, Fixed):
                extents[index] = min(remaining, child.size.cells)
                remaining -= extents[index]
            else:
                flexible.append((index, child.size.weight))
        total = sum(weight for _, weight in flexible)
        if total:
            fractions = []
            for index, weight in flexible:
                extents[index], remainder = divmod(remaining * weight, total)
                fractions.append((-remainder, index))
            extra = remaining - sum(extents[index] for index, _ in flexible)
            for _, index in sorted(fractions)[:extra]:
                extents[index] += 1
        regions = []
        cursor = self._padding
        cross = max(0, cross - 2 * self._padding)
        for extent in extents:
            regions.append(
                (cursor, self._padding, extent, cross)
                if horizontal
                else (self._padding, cursor, cross, extent)
            )
            cursor += extent + self._gap
        return tuple(regions)

    def build(self, buffer: Buffer) -> ResizableAnimation:
        """Bind this single-use tree to buffer dimensions without calling factories.

        Pass this method as play(effect_factory=layout.build), or compose the
        returned animation in Scene. Nested layouts bind automatically. The
        built tree owns all supplied children, including zero-area slots; content
        that never becomes visible closes without starting or calling factories.
        Resize notifications reallocate existing children without restarting them.
        Once started, hidden children keep updating; initially hidden factories
        wait until first visible allocation. Closing releases every owned child.
        """
        layouts: list[_Layout] = []
        owners: set[int] = set()

        def visit(layout: _Layout) -> None:
            if layout._used:
                raise RuntimeError("Layout trees are single-use; construct a new tree")
            if id(layout) in owners:
                raise ValueError("A layout cannot own the same child twice")
            owners.add(id(layout))
            layouts.append(layout)
            for child in layout._children:
                if isinstance(child, Spacer) or child.content is None:
                    continue
                if isinstance(child.content, _Layout):
                    visit(child.content)
                elif id(child.content) in owners:
                    raise ValueError("A layout cannot own the same animation twice")
                else:
                    owners.add(id(child.content))

        visit(self)
        size = (buffer.width(), buffer.height())
        self.regions(size)
        for layout in layouts:
            layout._used = True
        return self._instantiate(buffer)

    def _instantiate(self, buffer: Buffer) -> _LayoutAnimation:
        return _LayoutAnimation(self, (buffer.width(), buffer.height()))


class Row(_Layout):
    """Arrange Slots/Spacers horizontally; Fixed/Flex sizes allocate columns.

    Cross-axis height fills the padded area. Use build as a player factory;
    nest Row/Column inside a Slot. See regions for shortage and rounding rules.
    """


class Column(_Layout):
    """Arrange Slots/Spacers vertically; Fixed/Flex sizes allocate rows.

    Cross-axis width fills the padded area. Use build as a player factory;
    nest Row/Column inside a Slot. See regions for shortage and rounding rules.
    """

    _axis: Literal["row", "column"] = "column"


def _discard(content: Animation | Row | Column | None) -> None:
    if isinstance(content, _Layout):
        with ExitStack() as cleanup:
            for child in content._children:
                if isinstance(child, Slot):
                    cleanup.callback(_discard, child.content)
    elif content is not None:
        content.close()


class _Cell:
    def __init__(self, child: Slot | Spacer, region: tuple[int, int, int, int]) -> None:
        self._child, self._region = child, region
        self._visible = True
        self._panel: Panel | None = None
        self._closed = False

    @property
    def finished(self) -> bool | None:
        return self._panel.finished if self._panel is not None else None

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        if self._panel is not None:
            self._panel.set_visible(
                visible and bool(self._region[2] and self._region[3])
            )

    def reflow(self, region: tuple[int, int, int, int], *, started: bool) -> None:
        self._region = region
        x, y, width, height = region
        if self._panel is not None:
            self._panel.move_to((x, y))
            if width and height:
                self._panel.resize((width, height))
        elif started:
            self.start()
        self.set_visible(self._visible)

    def start(self) -> None:
        if self._panel is not None:
            return
        x, y, width, height = self._region
        child = self._child
        if isinstance(child, Spacer) or not width or not height:
            return
        factory = child.effect_factory
        content = child.content
        if isinstance(content, _Layout):
            factory = content._instantiate
            content = None
        elif content is not None:
            # Supplied content may first become visible after a resize, or be a
            # fitting panel whose initial size differs from this allocation.
            _resize(content, (width, height))
        self._panel = Panel(
            content,
            effect_factory=factory,
            size=(width, height),
            position=(x, y),
            border=False,
            fit=True,
            background=None,
        )
        self._panel.set_visible(self._visible)
        self._panel.start()

    def update(self, dt: float) -> None:
        if self._panel is not None:
            self._panel.update(dt)

    def draw(self, buffer: Buffer) -> None:
        if self._panel is not None and self._region[2] and self._region[3]:
            # A fitted bordered child can exceed a one-cell slot. Drawing through
            # the outer borderless panel keeps every pixel within its allocation.
            self._panel.draw(buffer)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._panel is not None:
            self._panel.close()
        elif isinstance(self._child, Slot):
            _discard(self._child.content)


class _LayoutAnimation:
    def __init__(self, layout: _Layout, size: tuple[int, int]) -> None:
        self._layout = layout
        self._size = size
        self._cells = [
            _Cell(child, region)
            for child, region in zip(layout._children, layout.regions(size))
        ]

        def background(buffer: Buffer) -> None:
            buffer.clear_buffer(val=layout._background)

        self._scene = Scene(CallbackEffect(background), *self._cells)
        self._started = self._closed = False

    @property
    def finished(self) -> bool | None:
        return self._scene.finished

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("Layout animations are single-use")
        if self._started:
            return
        self._started = True
        try:
            self._scene.start()
        except BaseException:
            self.close()
            raise

    def update(self, dt: float) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Layout must be started and not closed before update")
        self._scene.update(dt)

    def set_visible(self, visible: bool) -> None:
        """Propagate ancestor visibility to focus targets, preserving updates."""
        if type(visible) is not bool:
            raise TypeError("visible must be a bool")
        for cell in self._cells:
            _set_visible(cell, visible)

    def resize(self, size: tuple[int, int]) -> None:
        """Reflow without replacing live children or resetting clocks."""
        _size(size)
        if self._closed:
            raise RuntimeError("Cannot resize a closed layout")
        for cell, region in zip(self._cells, self._layout.regions(size)):
            cell.reflow(region, started=self._started)
        self._size = size

    def draw(self, buffer: Buffer) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Layout must be started and not closed before draw")
        if (buffer.width(), buffer.height()) != self._size:
            raise ValueError("Layout drawing buffer must match its bound dimensions")
        self._scene.draw(buffer)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with ExitStack() as cleanup:
            for cell in self._cells:
                cleanup.callback(cell.close)
            cleanup.callback(self._scene.close)
