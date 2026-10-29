"""Immutable single-cell tile maps with drawing and integer swept movement."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .bruhutil.bruhffer import Buffer
from .camera import Camera2D
from .geometry import Point, Rect, _clip, _integers, _rect
from .grid import _glyph


@dataclass(frozen=True, slots=True)
class Tile:
    """A cell glyph and independent collision flag; None is visually transparent."""

    glyph: str | None
    solid: bool = False

    def __post_init__(self) -> None:
        if self.glyph is not None:
            _glyph(self.glyph)
        if type(self.solid) is not bool:
            raise TypeError("solid must be a bool")


@dataclass(frozen=True, slots=True, init=False)
class TileMap:
    """Copy a nonempty rectangle of string tile IDs and its Tile definitions.

    IDs may be multi-character strings when supplied as cell sequences. Plain
    string rows naturally use one character per ID. Maps and tiles are immutable
    data, may be shared, and own no animations/resources. Draw multiple maps in
    order for visual layers; choose the collision map explicitly. All coordinates
    and sizes are integer world cells, one tile per terminal cell.
    """

    rows: tuple[tuple[str, ...], ...]
    tiles: Mapping[str, Tile]

    def __init__(
        self, rows: Sequence[Sequence[str]], tiles: Mapping[str, Tile]
    ) -> None:
        definitions = dict(tiles)
        if any(not isinstance(key, str) or not key for key in definitions):
            raise ValueError("tile IDs must be nonempty strings")
        if any(not isinstance(tile, Tile) for tile in definitions.values()):
            raise TypeError("tile definitions must be Tile instances")
        copied = tuple(tuple(row) for row in rows)
        if (
            not copied
            or not copied[0]
            or any(len(row) != len(copied[0]) for row in copied)
        ):
            raise ValueError("tile rows must form a nonempty rectangle")
        for row in copied:
            for key in row:
                if not isinstance(key, str) or key not in definitions:
                    raise ValueError(f"unknown tile ID: {key!r}")
        object.__setattr__(self, "rows", copied)
        object.__setattr__(self, "tiles", MappingProxyType(definitions))

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def tile_at(self, point: Point) -> Tile:
        """Look up one world cell; raise IndexError outside the map (no negative wrap)."""
        _integers(point, 2, "point")
        x, y = point
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError("cell is outside the map")
        return self.tiles[self.rows[y][x]]

    def collides(self, bounds: Rect, *, outside_solid: bool = True) -> bool:
        """Test solid tiles intersecting a half-open cell rectangle.

        Zero-area rectangles never collide. Outside cells block by default;
        outside_solid=False tests only the intersection with the map. Queries
        inspect at most the map area, regardless of offscreen rectangle size.
        """
        _rect(bounds, "bounds")
        if type(outside_solid) is not bool:
            raise TypeError("outside_solid must be a bool")
        x, y, width, height = bounds
        if width == 0 or height == 0:
            return False
        if outside_solid and (
            x < 0 or y < 0 or x + width > self.width or y + height > self.height
        ):
            return True
        return any(
            self.tiles[self.rows[row][column]].solid
            for row in range(max(0, y), min(self.height, y + height))
            for column in range(max(0, x), min(self.width, x + width))
        )

    def move(self, bounds: Rect, delta: Point) -> Point:
        """Sweep an unblocked, nonempty cell rectangle; return its new top-left.

        Resolve X then Y, sliding on the second axis. Every crossed leading edge
        is checked, preventing tunneling for arbitrarily large integer movement.
        The map boundary is solid. An overlapping/outside starting rectangle
        raises ValueError. Work is bounded by map dimensions; no simulation,
        position, camera or map state is mutated. This is grid movement, not
        continuous physics or a diagonal swept-body solver.
        """
        _rect(bounds, "bounds")
        _integers(delta, 2, "delta")
        x, y, width, height = bounds
        if width == 0 or height == 0 or self.collides(bounds):
            raise ValueError(
                "movement requires a nonempty unblocked starting rectangle"
            )
        dx, dy = delta
        goal_x = max(0, min(x + dx, self.width - width))
        if goal_x > x:
            for column in range(x + width, goal_x + width):
                if self.collides((column, y, 1, height)):
                    goal_x = column - width
                    break
        elif goal_x < x:
            for column in range(x - 1, goal_x - 1, -1):
                if self.collides((column, y, 1, height)):
                    goal_x = column + 1
                    break
        x = goal_x
        goal_y = max(0, min(y + dy, self.height - height))
        if goal_y > y:
            for row in range(y + height, goal_y + height):
                if self.collides((x, row, width, 1)):
                    goal_y = row - height
                    break
        elif goal_y < y:
            for row in range(y - 1, goal_y - 1, -1):
                if self.collides((x, row, width, 1)):
                    goal_y = row + 1
                    break
        return x, goal_y

    def draw(
        self,
        buffer: Buffer,
        *,
        camera: Camera2D | None = None,
        origin: Point = (0, 0),
        clip: Rect | None = None,
    ) -> None:
        """Paint only visible cells, without changing camera, map or caller's old frames.

        Origin places the view in the destination. Camera viewport and optional
        clip both restrict drawing; clip uses destination coordinates. A missing
        camera uses world origin (0, 0) and the entire destination. Spaces paint;
        None leaves lower layers visible. No implicit centering or resizing.
        """
        _integers(origin, 2, "origin")
        if camera is not None and not isinstance(camera, Camera2D):
            raise TypeError("camera must be a Camera2D or None")
        left, top, right, bottom = _clip(buffer, clip)
        ox, oy = origin
        cx, cy = camera.position if camera is not None else (0, 0)
        if camera is not None:
            left, top = max(left, ox), max(top, oy)
            right, bottom = (
                min(right, ox + camera.viewport[0]),
                min(bottom, oy + camera.viewport[1]),
            )
        for row in range(max(0, top - oy + cy), min(self.height, bottom - oy + cy)):
            for column in range(
                max(0, left - ox + cx), min(self.width, right - ox + cx)
            ):
                glyph = self.tiles[self.rows[row][column]].glyph
                if glyph is not None:
                    buffer.put_char(ox + column - cx, oy + row - cy, glyph)
