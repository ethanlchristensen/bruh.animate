"""Explicit cell-space camera state, independent of animation ownership."""

from .geometry import Point, Rect, _integers, _rect
from .resize import _size


class Camera2D:
    """Translate integer world cells into a viewport, with bounded follow.

    Position is the world cell at the viewport's top left. ``world_size``, when
    supplied, clamps the viewport to a world starting at (0, 0). A world smaller
    than the viewport stays at the top left. Without world_size, negative camera
    positions are allowed. No scaling or cell-aspect correction is performed.

    This is mutable state, not an Animation or lifecycle owner. Call follow and
    resize explicitly during updates/layout; transformations and drawing never
    change it. Cameras can be borrowed by multiple draws in one view.
    """

    def __init__(
        self,
        viewport: Point,
        *,
        position: Point = (0, 0),
        world_size: Point | None = None,
    ) -> None:
        _size(viewport)
        if world_size is not None:
            _size(world_size)
        self._viewport = viewport
        self._world_size = world_size
        self.position = position

    @property
    def viewport(self) -> Point:
        return self._viewport

    @property
    def world_size(self) -> Point | None:
        return self._world_size

    @property
    def position(self) -> Point:
        return self._position

    @position.setter
    def position(self, point: Point) -> None:
        _integers(point, 2, "position")
        if self.world_size is not None:
            point = (
                max(0, min(point[0], max(0, self.world_size[0] - self.viewport[0]))),
                max(0, min(point[1], max(0, self.world_size[1] - self.viewport[1]))),
            )
        self._position = point

    @property
    def visible_bounds(self) -> Rect:
        """World-space (x, y, width, height), including any area beyond a small world."""
        return (*self.position, *self.viewport)

    def resize(self, size: Point) -> None:
        """Resize the view and clamp existing position; do not follow a target implicitly."""
        _size(size)
        self._viewport = size
        self.position = self.position

    def follow(self, target: Point, *, dead_zone: Rect | None = None) -> None:
        """Move just enough to keep a target cell inside the viewport's dead zone.

        The default zone is the center cell (right/bottom center for even sizes).
        An explicit zone is (x, y, width, height) relative to the viewport, must
        be nonempty and fit inside it. World clamping takes precedence near edges.
        This operation is immediate, without smoothing or a hidden clock.
        """
        _integers(target, 2, "target")
        width, height = self.viewport
        zone = dead_zone if dead_zone is not None else (width // 2, height // 2, 1, 1)
        _rect(zone, "dead_zone")
        x, y, w, h = zone
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            raise ValueError("dead_zone must be nonempty and inside the viewport")
        cx, cy = self.position
        tx, ty = target
        self.position = (
            min(cx, tx - x) if tx < cx + x else max(cx, tx - x - w + 1),
            min(cy, ty - y) if ty < cy + y else max(cy, ty - y - h + 1),
        )

    def world_to_screen(self, point: Point, *, origin: Point = (0, 0)) -> Point:
        """Translate without clipping; origin is the screen placement of the viewport."""
        _integers(point, 2, "point")
        _integers(origin, 2, "origin")
        return point[0] - self.position[0] + origin[0], point[1] - self.position[
            1
        ] + origin[1]

    def screen_to_world(self, point: Point, *, origin: Point = (0, 0)) -> Point:
        """Inverse translation, including points outside the viewport."""
        _integers(point, 2, "point")
        _integers(origin, 2, "origin")
        return point[0] + self.position[0] - origin[0], point[1] + self.position[
            1
        ] - origin[1]
