"""
Copyright 2023 Ethan Christensen

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

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil import Buffer
from .base_effect import BaseEffect
from .settings import AutomatonSettings


def _heat(r: float) -> int:
    r = max(0.0, min(1.0, r))
    if r < 0.25:
        return 17 + int(r * 4 * 18)
    elif r < 0.5:
        return 51 + int((r - 0.25) * 4 * 12)
    elif r < 0.75:
        return 82 + int((r - 0.5) * 4 * 12)
    else:
        return 220 + int((r - 0.75) * 4 * 3)


class AutomatonEffect(BaseEffect):
    """
    Wolfram 1-D elementary cellular automaton.

    Each generation is computed from the previous row using a 3-cell
    neighbourhood lookup table determined by the rule number (0–255).
    New generations scroll downward from the top, producing a 2-D
    space-time diagram. Rule 30 (default) is chaotic; Rule 90 produces
    Sierpinski triangles; Rule 110 is Turing-complete.

    Call :meth:`set_rule` to switch rules and reset the seed mid-run.
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: AutomatonSettings = None
    ):
        super().__init__(buffer, background)
        s = settings or AutomatonSettings()

        self.color = s.color
        self.char = s.char
        self._w = buffer.width()
        self._h = buffer.height()

        self._row = np.zeros(self._w, dtype=np.uint8)
        self._row[self._w // 2] = 1
        self._rule_table = self._make_table(s.rule)

    @staticmethod
    def _make_table(rule_num: int) -> np.ndarray:
        return np.array([(int(rule_num) >> i) & 1 for i in range(8)], dtype=np.uint8)

    def set_rule(self, rule_num: int):
        """Switch to a new rule number (0–255) and reset the initial seed."""
        self._rule_table = self._make_table(rule_num)
        self._row[:] = 0
        self._row[self._w // 2] = 1
        self.buffer.clear_buffer(val=self.background)

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        # Compute next generation
        left = np.roll(self._row, 1)
        right = np.roll(self._row, -1)
        idx = (left * 4 + self._row * 2 + right).astype(int)
        next_row = self._rule_table[idx]

        # Scroll buffer down and insert new row at top
        self.buffer.buffer.insert(0, [self.background] * self._w)
        self.buffer.buffer.pop()

        # Color each live cell by its horizontal position
        for col, alive in enumerate(next_row):
            if alive:
                ratio = col / max(1, self._w - 1)
                color = _heat(ratio) if self.color else None
                ch = bc(self.char, color=color) if color is not None else self.char
                self.buffer.buffer[0][col] = ch

        self._row = next_row
