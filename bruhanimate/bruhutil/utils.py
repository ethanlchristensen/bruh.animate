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

import sys
import time


def sleep(s):
    sys.stdout.flush()
    time.sleep(s)


from .bruhtypes import valid_effect_types

VALID_EFFECTS = sorted(valid_effect_types)

HORIZONTAL = "horizontal"

VERTICAL = "vertical"

INF = float("inf")

LIFE_COLORS = {
    "GREYSCALE": [232, 235, 239, 241, 244, 247, 248, 250, 254, 231],
    "GREYSCALE_r": [232, 235, 239, 241, 244, 247, 248, 250, 254, 231][::-1],
    "GREYSCALE_MUTED": [232, 235, 235, 239, 239, 241, 241, 244, 244, 231],
    "RAINBOW": [232, 202, 208, 190, 112, 27, 105, 129, 161, 231],
    "RAINBOW_r": [231, 196, 208, 190, 112, 27, 105, 129, 161, 201][::-1],
}

LIFE_SCALES = {
    "default": " .:-=+*%#@",
    ".": " .........",
    "o": " ooooooooo",
    "0": " 000000000",
}

PLASMA_COLORS = {
    2: [[232, 231]],
    8: [
        [150, 93, 11, 38, 181, 250, 143, 12],
        [142, 167, 216, 161, 59, 228, 148, 219],
        [196, 202, 220, 76, 45, 27, 177, 129][::-1],
    ],
    10: [[232, 16, 53, 55, 89, 91, 126, 163, 197, 196][::-1]],
    16: [
        [
            232,
            16,
            53,
            55,
            56,
            89,
            90,
            91,
            125,
            126,
            163,
            199,
            198,
            197,
            196,
            39,
            81,
            231,
        ][::-1],
        [195, 106, 89, 176, 162, 180, 201, 233, 124, 252, 104, 181, 2, 182, 4, 170],
    ],
}

PLASMA_VALUES = [[43, 15, 8, 24], [15, 42, 47, 23], [35, 29, 31, 27], [10, 26, 19, 41]]

GRADIENTS = [
    [21, 57, 93, 129, 165, 201, 165, 129, 93, 57],
]

VALID_DIRECTIONS = ["right", "left"]

OLD_GREY_SCALES = [" .:;rsA23hHG#9&@"]

GREY_SCALES = [" .,:ilwW", " .,:ilwW%@", " .:;rsA23hHG#9&@"]

WIND_DIRECTIONS = ["east", "west", "none"]

NOISE = "!@#$%^&*()_+1234567890-=~`qazwsxedcrfvtgbyhnujmik,ol.p;/[']\\QAZXSWEDCVFRTGBNHYUJM<KIOL>?:P{\"}|"

SNOWFLAKE_TYPES = {
    ".": {"speed": 5},
    ",": {"speed": 4},
    "+": {"speed": 3},
    "*": {"speed": 2},
    "x": {"speed": 1},
}

SNOWFLAKE_COLORS = {
    ".": 238,
    ",": 244,
    "+": 250,
    "*": 254,
    "x": 231,
}

FLAKE_WEIGHT_CHARS = {1: ".", 4: "-", 7: "~", 12: "=", 18: "#"}

TWINKLE_COLORS = {idx: val for idx, val in enumerate(range(232, 256))}
