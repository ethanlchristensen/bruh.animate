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

import random

from bruhcolor import bruhcolored

from ..bruhutil import LIFE_COLORS, LIFE_SCALES, Buffer
from .base_effect import BaseEffect
from .settings import GameOfLifeSettings


class GameOfLifeEffect(BaseEffect):
    """
    Effect to simulate Conway's Game of Life.
    """

    def __init__(
        self,
        buffer: Buffer,
        background: str,
        settings: GameOfLifeSettings = None,
    ):
        """
        Initializes the GameOfLifeEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (GameOfLifeSettings, optional): Configuration for the effect. Defaults to None.
        """
        super(GameOfLifeEffect, self).__init__(buffer, background)
        s = settings or GameOfLifeSettings()

        self.decay = s.decay
        self.scale = s.scale
        self.color = s.color
        self.color_type = s.color_type
        self._set_attributes()

        self.directions = [
            [1, 0],
            [0, 1],
            [-1, 0],
            [0, -1],
            [1, 1],
            [1, -1],
            [-1, 1],
            [-1, -1],
        ]
        self.rules = {"life": [2, 3], "death": [3, 3]}
        self.board = [
            [" " for _ in range(self.buffer.width())]
            for __ in range(self.buffer.height())
        ]
        self._tick = 0

    def _set_attributes(self):
        self.grey_scale = (
            LIFE_SCALES[random.choice(list(LIFE_SCALES.keys()))]
            if self.decay and self.scale == "random"
            else LIFE_SCALES[self.scale]
            if self.decay
            else " o"
        )
        self.colors = [232, 231] if not self.decay else LIFE_COLORS[self.color_type]
        self.ALIVE = len(self.grey_scale) - 1
        self.DEAD = 0
        self.mappings = {i: self.grey_scale[i] for i in range(len(self.grey_scale))}

    def set_decay(
        self, decay: bool, color_type: str = "GREYSCALE", scale: str = "random"
    ):
        """
        Enables or disables cell decay and selects the color/scale scheme.

        Args:
            decay (bool): Whether cells should decay after dying.
            color_type (str, optional): Color palette key. Defaults to "GREYSCALE".
            scale (str, optional): Grey scale key. Defaults to "random".
        """
        self.decay = decay
        self.scale = scale
        if color_type:
            self.color_type = color_type
        self._set_attributes()

    def set_rules(self, life_rule: list[int], death_rule: list[int]):
        """
        Updates the rules for cell survival and birth.

        Args:
            life_rule (list[int]): [min, max] neighbor count for a live cell to survive.
            death_rule (list[int]): [min, max] neighbor count for a dead cell to become alive.
        """
        self.rules["life"] = life_rule
        self.rules["death"] = death_rule

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        tick = self._tick
        self._tick += 1
        if tick == 0:
            for y in range(self.buffer.height()):
                for x in range(self.buffer.width()):
                    if random.random() < 0.1:
                        self.buffer.put_char(
                            x,
                            y,
                            bruhcolored(
                                self.grey_scale[self.ALIVE],
                                color=self.colors[self.ALIVE],
                            ).colored,
                        )
                        self.board[y][x] = (
                            bruhcolored(
                                self.grey_scale[self.ALIVE],
                                color=self.colors[self.ALIVE],
                            ),
                            self.ALIVE,
                        )
                    else:
                        self.buffer.put_char(
                            x,
                            y,
                            bruhcolored(
                                self.grey_scale[self.DEAD], color=self.colors[self.DEAD]
                            ).colored,
                        )
                        self.board[y][x] = (
                            bruhcolored(
                                self.grey_scale[self.DEAD], color=self.colors[self.DEAD]
                            ),
                            0,
                        )
        else:
            all_neighbors = [
                [0 for _ in range(self.buffer.width())]
                for __ in range(self.buffer.height())
            ]
            for y in range(len(all_neighbors)):
                for x in range(len(all_neighbors[y])):
                    neighbors = 0
                    for direction in self.directions:
                        if (
                            0 <= y + direction[0] < self.buffer.height()
                            and 0 <= x + direction[1] < self.buffer.width()
                            and self.board[y + direction[0]][x + direction[1]][1]
                            == self.ALIVE
                        ):
                            neighbors += 1
                    all_neighbors[y][x] = neighbors

            for y in range(self.buffer.height()):
                for x in range(self.buffer.width()):
                    if self.board[y][x][1] == self.ALIVE:
                        if (
                            self.rules["life"][0]
                            <= all_neighbors[y][x]
                            <= self.rules["life"][1]
                        ):
                            pass
                        else:
                            self.buffer.put_char(
                                x,
                                y,
                                bruhcolored(
                                    self.grey_scale[self.ALIVE - 1],
                                    color=self.colors[self.ALIVE - 1],
                                ).colored,
                            )
                            self.board[y][x] = (
                                bruhcolored(
                                    self.grey_scale[self.ALIVE - 1],
                                    color=self.colors[self.ALIVE - 1],
                                ),
                                self.ALIVE - 1,
                            )
                    else:
                        if (
                            self.rules["death"][0]
                            <= all_neighbors[y][x]
                            <= self.rules["death"][1]
                        ):
                            self.buffer.put_char(
                                x,
                                y,
                                bruhcolored(
                                    self.grey_scale[self.ALIVE],
                                    color=self.colors[self.ALIVE],
                                ).colored,
                            )
                            self.board[y][x] = (
                                bruhcolored(
                                    self.grey_scale[self.ALIVE],
                                    color=self.colors[self.ALIVE],
                                ),
                                self.ALIVE,
                            )
                        else:
                            pos = max(0, self.board[y][x][1] - 1)
                            self.buffer.put_char(
                                x,
                                y,
                                bruhcolored(
                                    self.grey_scale[pos],
                                    color=self.colors[pos],
                                ).colored,
                            )
                            self.board[y][x] = (
                                bruhcolored(
                                    self.grey_scale[pos], color=self.colors[pos]
                                ),
                                pos,
                            )
