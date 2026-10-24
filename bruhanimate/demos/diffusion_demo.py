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

"""Cycle through diffusion configurations using one Player. q quits."""

from bruhanimate import Buffer, ResizePolicy, effect_registry, play
from bruhanimate.bruheffect import DiffusionSettings

from ._showcase import Showcase

TARGET_FPS = 30
PHASE_FRAMES = 500


def build(buffer):
    phases = [
        (
            "Coral pattern  (f=0.0545, k=0.062)",
            DiffusionSettings(
                f=0.0545,
                k=0.062,
                color=True,
                steps_per_frame=8,
                shading=True,
                seed_pattern="scattered",
            ),
        ),
        (
            "Spot pattern   (f=0.035,  k=0.065)",
            DiffusionSettings(
                f=0.035,
                k=0.065,
                color=True,
                steps_per_frame=8,
                shading=True,
                seed_pattern="scattered",
            ),
        ),
        (
            "Stripe pattern (f=0.026,  k=0.051)",
            DiffusionSettings(
                f=0.026,
                k=0.051,
                color=True,
                steps_per_frame=8,
                shading=True,
                seed_pattern="scattered",
            ),
        ),
    ]
    return Showcase(
        [
            (
                label,
                effect_registry.create(
                    "diffusion",
                    buffer if i == 0 else Buffer(buffer.height(), buffer.width()),
                    " ",
                    settings=config,
                ),
            )
            for i, (label, config) in enumerate(phases)
        ],
        duration=PHASE_FRAMES / 30,
        title="Diffusion",
    )


def run(*, frames=None, fps=TARGET_FPS, on_resize: ResizePolicy = "resize"):
    return play(
        effect_factory=build,
        frames=frames,
        fps=fps,
        updates_per_second=30,
        on_resize=on_resize,
    )


if __name__ == "__main__":
    run()
