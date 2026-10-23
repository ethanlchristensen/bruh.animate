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

"""Build content from buffer dimensions; Player handles playback."""

from bruhanimate import DrawLinesEffect, DrawLinesSettings, play


def build(buffer):
    effect = DrawLinesEffect(buffer, " ", DrawLinesSettings(thin=False))
    w, h = buffer.width(), buffer.height()
    left, right = w // 5, w - 1 - w // 5
    top, bottom = h // 5, h - 1 - h // 5
    effect.add_line((left, top), (right, top))
    effect.add_line((right, top), (w // 2, bottom))
    effect.add_line((w // 2, bottom), (left, top))
    effect.add_line((w // 2, 0), (w // 2, bottom))
    return effect


def run(*, frames=None, fps=30):
    return play(effect_factory=build, frames=frames, fps=fps, updates_per_second=30)


if __name__ == "__main__":
    run()
