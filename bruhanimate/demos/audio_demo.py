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

"""Cycle through audio configurations using one Player. q quits."""

from bruhanimate import Buffer, effect_registry, play
from bruhanimate.bruheffect import AudioSettings

from ._showcase import Showcase

TARGET_FPS = 30
PHASE_FRAMES = 300


def build(buffer):
    phases = [
        ("Bars", AudioSettings(mode="bars", color=True, smoothing=0.5)),
        ("Mirror", AudioSettings(mode="mirror", color=True, smoothing=0.5)),
        ("Waveform", AudioSettings(mode="waveform", color=True, smoothing=0.1)),
        ("Spectrum", AudioSettings(mode="spectrum", color=True, smoothing=0.2)),
        ("Radial", AudioSettings(mode="radial", color=True, smoothing=0.3)),
        ("Rain", AudioSettings(mode="rain", color=True, smoothing=0.2)),
        ("Tunnel", AudioSettings(mode="tunnel", color=True, smoothing=0.2)),
        (
            "Ripple",
            AudioSettings(mode="ripple", color=True, smoothing=0.15, sensitivity=1.5),
        ),
        ("Vortex", AudioSettings(mode="vortex", color=True, smoothing=0.2)),
        ("Wave", AudioSettings(mode="wave", color=True, smoothing=0.25)),
        ("Starfield", AudioSettings(mode="starfield", color=True, smoothing=0.2)),
        (
            "Fireworks",
            AudioSettings(
                mode="fireworks", color=True, smoothing=0.15, sensitivity=2.0
            ),
        ),
        ("Interference", AudioSettings(mode="interference", color=True, smoothing=0.2)),
        ("Bounce", AudioSettings(mode="bounce", color=True, smoothing=0.2)),
        (
            "Lightning",
            AudioSettings(mode="lightning", color=True, smoothing=0.1, sensitivity=1.5),
        ),
        ("Aurora", AudioSettings(mode="aurora", color=True, smoothing=0.3)),
        ("Orbit", AudioSettings(mode="orbit", color=True, smoothing=0.2)),
        (
            "Orbit Gradient",
            AudioSettings(mode="orbit_gradient", color=True, smoothing=0.2),
        ),
        (
            "Scope",
            AudioSettings(mode="scope", color=True, smoothing=0.0, sensitivity=3.0),
        ),
        ("Grid", AudioSettings(mode="grid", color=True, smoothing=0.2)),
        ("Helix", AudioSettings(mode="helix", color=True, smoothing=0.25)),
        ("Lissajous", AudioSettings(mode="lissajous", color=True, smoothing=0.2)),
        ("Sunburst", AudioSettings(mode="sunburst", color=True, smoothing=0.2)),
        ("Mandala", AudioSettings(mode="mandala", color=True, smoothing=0.25)),
        (
            "Comet",
            AudioSettings(mode="comet", color=True, smoothing=0.15, sensitivity=1.5),
        ),
        ("Weave", AudioSettings(mode="weave", color=True, smoothing=0.2)),
    ]
    return Showcase(
        [
            (
                label,
                effect_registry.create(
                    "audio",
                    buffer if i == 0 else Buffer(buffer.height(), buffer.width()),
                    " ",
                    settings=config,
                ),
            )
            for i, (label, config) in enumerate(phases)
        ],
        duration=PHASE_FRAMES / 30,
        title="Audio",
    )


def run(*, frames=None, fps=TARGET_FPS):
    return play(effect_factory=build, frames=frames, fps=fps, updates_per_second=30)


if __name__ == "__main__":
    run()
