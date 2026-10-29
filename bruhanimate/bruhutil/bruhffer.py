"""
Copyright 2023 Ethan Christensen
Copied, Guided, and Adapted from Asciimatics <https://github.com/peterbrittain/asciimatics/blob/master/asciimatics/screen.py>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Self


class Buffer:
    """
    Class for creating and managing a buffer
    """

    def __init__(self, height: int, width: int) -> None:
        if height < 0 or width < 0:
            raise ValueError("Buffer dimensions must be non-negative")
        self._height = height
        self._width = width
        self._center = self._width // 2
        self._empty_line = [" " for _ in range(self._width)]
        self.buffer: list[list[Any]] = [
            self._empty_line[:] for _ in range(self._height)
        ]

    def get_buffer_changes(self, in_buf: Buffer) -> Iterator[tuple[int, int, Any]]:
        """
        Compare this buffer with the given buffer and yield differences.

        Args:
            in_buf (Buffer): The buffer to compare with.

        Yields:
            Tuple[int, int, str]: A tuple containing the row index, column index,
                                  and the character from the input buffer that
                                  differs.
        """
        self._validate_dimensions(in_buf)

        for y in range(self._height):
            if self.buffer[y] == in_buf.buffer[y]:
                continue
            for x in range(self._width):
                if self.buffer[y][x] != in_buf.buffer[y][x]:
                    yield y, x, in_buf.buffer[y][x]

    def clear_buffer(
        self,
        x: int = 0,
        y: int = 0,
        w: int | None = None,
        h: int | None = None,
        val: Any = " ",
    ) -> Self:
        """
        Clear a rectangle, clipped to the buffer bounds.

        Negative origins are allowed. Nonpositive sizes and rectangles entirely
        outside the buffer have no effect. None can be used as a transparent fill.

        Args:
            x (int): The starting x-coordinate for the clear operation (default is 0).
            y (int): The starting y-coordinate for the clear operation (default is 0).
            w (int, optional): The width of the section to be cleared. If not specified,
                               clears to the end of the buffer's width.
            h (int, optional): The height of the section to be cleared. If not specified,
                               clears to the end of the buffer's height.
            val (str): The character to fill the cleared area with (default is a space).
        """
        right = self._width if w is None else min(self._width, x + w)
        bottom = self._height if h is None else min(self._height, y + h)
        left = max(0, x)
        top = max(0, y)
        if right <= left or bottom <= top:
            return self

        line = [val for _ in range(right - left)]

        if left == 0 and top == 0 and right == self._width and bottom == self._height:
            self.buffer = [line[:] for _ in range(self._height)]
        else:
            for i in range(top, bottom):
                self.buffer[i][left:right] = line[:]

        return self

    def get_char(self, x: int, y: int) -> Any:
        """
        Get the character at the specified location.

        Parameters:
            x (int): The column index.
            y (int): The row index.
        Returns:
            str or None: The character at the specified location, or None if out of bounds.
        """
        if 0 <= y < self._height and 0 <= x < self._width:
            return self.buffer[y][x]
        return None

    def put_char(self, x: int, y: int, val: Any, transparent: bool = False) -> None:
        """
        Place a character at the specified location.

        Parameters:
            x (int): The column index.
            y (int): The row index.
            val (str): The character to place.
            transparent (bool): If True, only place non-space characters.
        """
        if 0 <= y < self._height and 0 <= x < self._width:
            if self.buffer[y][x] != val:
                if transparent and val != " ":
                    self.buffer[y][x] = val
                elif not transparent:
                    self.buffer[y][x] = val

    def put_at(
        self, x: int, y: int, text: Sequence[Any], transparent: bool = False
    ) -> None:
        """
        Place text starting at the specified location.

        Parameters:
            x (int): The starting column index.
            y (int): The row index.
            text (str): The text to place.
            transparent (bool): If True, only place non-space characters.
        """
        if x < 0:
            text = text[-x:]
            x = 0

        if x + len(text) > self._width:
            text = text[: self._width - x]

        if not transparent:
            for i, c in enumerate(text):
                self.put_char(x + i, y, c)
        else:
            for i, c in enumerate(text):
                if c != " ":
                    self.put_char(x + i, y, c)

    def put_at_center(
        self, y: int, text: Sequence[Any], transparent: bool = False
    ) -> None:
        """
        Place text centered on the specified row.

        Parameters:
            y (int): The row index to place the text.
            text (str): The text to place.
            transparent (bool): If True, only place non-space characters.
        """
        if not transparent:
            x = self._center - len(text) // 2
            for i, c in enumerate(text):
                self.put_char(x + i, y, c)
        else:
            x = self._center - len(text) // 2
            for i, c in enumerate(text):
                if c != " ":
                    self.put_char(x + i, y, c)

    def scroll(self, shift: int) -> None:
        """
        Scroll the buffer up or down by a specified number of lines.

        Parameters:
            shift (int): The number of lines to scroll. Positive scrolls up, negative scrolls down.
        """
        if shift > 0:
            shift = min(shift, self._height)
            for y in range(0, self._height - shift):
                self.buffer[y] = self.buffer[y + shift]
            for y in range(self._height - shift, self._height):
                self.buffer[y] = self._empty_line[:]
        else:
            shift = max(shift, -self._height)
            for y in range(self._height - 1, -shift - 1, -1):
                self.buffer[y] = self.buffer[y + shift]
            for y in range(0, -shift):
                self.buffer[y] = self._empty_line[:]

    def shift_line(self, y: int, shift: int) -> None:
        """
        Rotate a row by cells: positive shifts right, negative shifts left.
        Amounts wrap modulo the width; empty rows are unchanged.
        Args:
            y (int): The index of the row to shift.
            shift (int): The amount by which to shift the row.
        """
        if self._width:
            shift %= self._width
            self.buffer[y] = self.buffer[y][-shift:] + self.buffer[y][:-shift]

    def shift(self, shift: int) -> None:
        """
        Rotate all rows using the same direction and wrapping as shift_line.
        Args:
            shift (int): The amount by which to shift each row.
        """
        for y in range(self._height):
            self.shift_line(y, shift)

    def grab_slice(self, x: int, y: int, width: int) -> list[Any]:
        """
        Grab a segment from a specific row in the buffer.

        Args:
            x (int): The starting column index for the slice.
            y (int): The row index from which to grab the slice.
            width (int): Number of characters to include in the slice.

        Returns:
            list: A list containing the specified segment of the row.
        """
        return self.buffer[y][x : x + width]

    def sync_with(self, in_buf: Buffer) -> None:
        """
        Synchronize this buffer with another buffer.
        Args:
            in_buf (Buffer): The buffer to synchronize with.
        """
        self._validate_dimensions(in_buf)
        for y in range(self._height):
            self.buffer[y][:] = in_buf.buffer[y][:]

    def sync_over_top(self, in_buf: Buffer) -> None:
        """
        Overlay non-None values from another buffer onto this buffer.

        Args:
            in_buf (Buffer): The buffer containing values to overlay.
        """
        self._validate_dimensions(in_buf)
        for y in range(self._height):
            for x in range(self._width):
                if in_buf.buffer[y][x] is not None:
                    self.buffer[y][x] = in_buf.buffer[y][x]

    def _validate_dimensions(self, in_buf: Buffer) -> None:
        if self._height != in_buf.height() or self._width != in_buf.width():
            raise ValueError("Buffer dimensions must match")

    def height(self) -> int:
        """
        Get the height of the buffer.
        Returns:
            int: The height of the buffer.
        """
        return self._height

    def width(self) -> int:
        """
        Get the width of the buffer.

        Returns:
            int: The width of the buffer.
        """
        return self._width
